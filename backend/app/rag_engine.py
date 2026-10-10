"""Replaceable local retrieval/generation interfaces, exact Qwen raw prompt budgeting."""
import asyncio
import json
import time
from typing import Protocol
import httpx
from .config import ROOT
from .ollama_local import URL, TAG
from .search_api import internal_key
from .grounding import GroundedOutput, ModelOutput, RagError, raw_prompt, expand_model_output, precheck, final_result


class Retriever(Protocol):
    async def retrieve(self,question,filters): ...


class Generator(Protocol):
    def budget(self,question,language,passages,repair=None): ...
    async def generate(self,prompt,tokens): ...


class LocalRetriever:
    def __init__(self,settings): self.key=internal_key(settings); self.url=settings.index_url
    async def retrieve(self,question,filters):
        async with httpx.AsyncClient(trust_env=False,timeout=20) as client:
            try:
                response=await client.post(self.url+'/query',
                    headers={'X-Index-Key':self.key},json={'question':question,'count':5,**filters})
                if response.status_code==422: raise RagError('query_token_limit')
                if response.status_code!=200: raise RagError('retrieval_unavailable')
                result=response.json()
            except httpx.HTTPError: raise RagError('retrieval_unavailable') from None
        if result.get('status')=='unavailable': raise RagError('retrieval_unavailable')
        if result.get('status') not in ('empty','results'): raise RagError('invalid_retrieval_response')
        return result


class LocalGenerator:
    def __init__(self,settings):
        self.manifest=json.loads((ROOT/'docs/llm_model.json').read_text('utf-8'))
        local=settings.data_dir.parent/'ollama'
        if not (local/'prepared.json').is_file() or json.loads((local/'prepared.json').read_text('utf-8'))!=self.manifest:
            raise RagError('llm_not_prepared')
        from transformers import AutoTokenizer
        self.tokenizer=AutoTokenizer.from_pretrained(str(local/'tokenizer'),local_files_only=True,trust_remote_code=False)

    def budget(self,question,language,passages,repair=None):
        selected=list(passages)
        while True:
            prompt=raw_prompt(question,language,selected,repair)
            tokens=len(self.tokenizer.encode(prompt,add_special_tokens=False))
            if tokens+self.manifest['output_tokens']+64<=self.manifest['context_tokens']:
                return prompt,tokens,selected,len(selected)<len(passages)
            if not selected: raise RagError('context_budget_exceeded')
            selected.pop()  # Whole passages only; never silently clips policy conditions.

    async def generate(self,prompt,tokens):
        return await self._generate(prompt,tokens,ModelOutput.model_json_schema(),self.manifest['output_tokens'])

    def judge_budget(self,system,data,schema):
        serialized=json.dumps(data,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e')
        prompt='<|im_start|>system\n'+system+'\nSCHEMA:\n'+json.dumps(schema)+'<|im_end|>\n<|im_start|>user\n'+serialized+'<|im_end|>\n<|im_start|>assistant\n'
        tokens=len(self.tokenizer.encode(prompt,add_special_tokens=False))
        if tokens+256+64>self.manifest['context_tokens']:raise RagError('verification_context_limit')
        return prompt,tokens

    async def judge(self,prompt,tokens,schema):
        return await self._generate(prompt,tokens,schema,256)

    async def _generate(self,prompt,tokens,schema,output_tokens):
        async with httpx.AsyncClient(trust_env=False,timeout=httpx.Timeout(60,connect=3)) as client:
            try:
                version=(await client.get(URL+'/api/version')).json()['version']
                if version!=self.manifest['ollama_version']: raise RagError('ollama_version_mismatch')
                tags=(await client.get(URL+'/api/tags')).json()['models']
                current=next((m for m in tags if m['name']==TAG),None)
                if not current or current['digest']!=self.manifest['digest']: raise RagError('llm_digest_mismatch')
                options={k:self.manifest[k] for k in ('temperature','seed')}
                options.update(num_ctx=self.manifest['context_tokens'],num_predict=output_tokens)
                payload={'model':TAG,'prompt':prompt,'raw':True,'stream':False,
                    'format':schema,'think':False,'keep_alive':'5m','options':options,'truncate':False,'shift':False}
                async with client.stream('POST',URL+'/api/generate',json=payload) as response:
                    if response.status_code!=200: raise RagError('ollama_unavailable')
                    raw=bytearray()
                    async for chunk in response.aiter_bytes():
                        raw.extend(chunk)
                        if len(raw)>65536: raise RagError('llm_response_limit')
                    result=json.loads(raw)
            except httpx.TimeoutException: raise RagError('generation_timeout') from None
            except (httpx.HTTPError,ValueError,KeyError): raise RagError('ollama_unavailable') from None
        if result.get('thinking') or '<think>' in result.get('response',''): raise RagError('unexpected_thinking_output')
        if result.get('done_reason')!='stop' or not result.get('done'): raise RagError('generation_truncated')
        if result.get('prompt_eval_count')!=tokens: raise RagError('llm_token_count_mismatch')
        if tokens+result.get('eval_count',0)>self.manifest['context_tokens']-64: raise RagError('llm_context_overrun')
        metrics={k:result.get(k) for k in ('total_duration','load_duration','prompt_eval_count','prompt_eval_duration','eval_count','eval_duration')}
        return result['response'],metrics


async def pipeline(question,language,filters,retriever,generator,verifier=None):
    started=time.perf_counter(); response=await retriever.retrieve(question,filters)
    passages=response['items']
    from .language import normalize
    state=precheck(normalize(question)['retrieval_question'],filters,passages,language)
    timings={'retrieval_ms':round((time.perf_counter()-started)*1000,2),'generation_attempts':0,
        'query_normalization':response.get('query_normalization',normalize(question))}
    if state:
        output=GroundedOutput(status=state,language=language,claims=[],limitations=[])
        return final_result(output,passages,language),passages,response.get('generation'),timings
    from .language import context_order
    original_count=len(passages)
    passages,rules=context_order(question,passages) if language=='hi' else (passages,[])
    context_omitted=len(passages)<original_count
    timings['context_selection']={'rules':rules,'passage_order':[p['chunk_id'] for p in passages],
        'notice':'Complete source excerpts prioritized before token budgeting; this is not claim support.'}
    failures={'invalid_structured_output','response_language_mismatch','invented_evidence_id','invented_quote_id','non_exact_evidence_quote','unsupported_numeric_claim','unsupported_claim_markup','contradictory_condition'}
    repair=None; attempts=[]; rejected=[]
    for _ in range(2):
        prompt,tokens,selected,omitted=generator.budget(question,language,passages,repair)
        omitted=omitted or context_omitted
        if not selected:
            output=GroundedOutput(status='insufficient_evidence',language=language,claims=[],limitations=['incomplete_context'])
            return final_result(output,[],language,True),[],response.get('generation'),timings
        raw,metrics=await generator.generate(prompt,tokens); attempts.append(metrics)
        timings.update(generation_attempts=len(attempts),inference=attempts)
        try: output=expand_model_output(raw,language,selected,question)
        except RagError as exc:
            if exc.code not in failures: raise
            repair=exc.code
            continue
        checks=[]
        if output.claims:
            from .language import hindi_annual,hindi_chatbot
            output,construction=hindi_annual(output,question,selected)
            if not construction:output,construction=hindi_chatbot(output,question,selected)
            if construction:timings['response_construction']=construction
            if verifier is None:raise RagError('verification_unavailable')
            output,checks,verification=await verifier.evaluate(output,selected,response.get('generation'))
            timings['verification']=verification
            if not output.claims and len(attempts)<2 and checks and all(c['assessment'].get('reason_code') in ('condition_omitted','scope_mismatch') for c in checks):
                rejected.extend(checks)
                repair='support_condition_or_scope_omitted'
                continue
        result=final_result(output,selected,language,omitted)
        result['_claim_checks']=rejected+checks
        result['grounding']='Exact SQL provenance + deterministic guards + same-model heuristic support judge; not independent fact verification.'
        from .support import METHOD
        result['support_method']=METHOD if checks else 'not_evaluated'
        result['limitations']=[v for v in result['limitations'] if 'full claim entailment' not in v and 'पूरे दावे का अर्थ' not in v]
        if checks:
            result['limitations'].append(('Automated support check is heuristic; the generator and judge use the same model. It is not a truth guarantee.',
                'स्वचालित समर्थन जाँच एक सीमित अनुमान है; उत्तर और जाँच में एक ही मॉडल है। यह सत्य की गारंटी नहीं है।')[language=='hi'])
        timings['pipeline_ms']=round((time.perf_counter()-started)*1000,2)
        return result,selected,response.get('generation'),timings
    raise RagError('grounding_validation_failed')

"""Explicit official model/tokenizer download. Never invoked by ordinary API startup."""
import json
from filelock import FileLock
import httpx
from app.config import Settings, ROOT
from app.ollama_local import OllamaHost, URL, TAG

if __name__ == '__main__':
    settings = Settings(); root = settings.data_dir.parent/'ollama'; root.mkdir(parents=True,exist_ok=True)
    lock=settings.owner_path('rag');lock.parent.mkdir(parents=True,exist_ok=True)
    with FileLock(str(lock),timeout=0), OllamaHost(settings):
        with httpx.Client(trust_env=False,timeout=120) as client:
            with client.stream('POST',URL+'/api/pull',json={'model':TAG,'stream':True}) as response:
                response.raise_for_status(); last = None
                for line in response.iter_lines():
                    item=json.loads(line)
                    if item.get('error'): raise RuntimeError('Official model pull failed')
                    progress=int(item.get('completed',0)*100/max(1,item.get('total',1)))
                    label=(item.get('status'),progress//10)
                    if label!=last: print(item.get('status'),progress,flush=True);last=label
            record=next(m for m in client.get(URL+'/api/tags').json()['models'] if m['name']==TAG)
            show=client.post(URL+'/api/show',json={'model':TAG}).json()
            ollama_version=client.get(URL+'/api/version').json()['version']
        from huggingface_hub import snapshot_download
        expected=ROOT/'docs/llm_model.json'
        revision=json.loads(expected.read_text('utf-8'))['tokenizer_revision'] if expected.exists() else httpx.get(
            'https://huggingface.co/api/models/Qwen/Qwen3-4B-Instruct-2507',trust_env=False,timeout=30).json()['sha']
        snapshot_download('Qwen/Qwen3-4B-Instruct-2507',revision=revision,local_dir=str(root/'tokenizer'),
            allow_patterns=['tokenizer*','config.json','special_tokens_map.json','chat_template.jinja'])
        manifest={'tag':TAG,'digest':record['digest'],'quantization':show['details']['quantization_level'],
            'parameters':show['details']['parameter_size'],'ollama_version':ollama_version,
            'tokenizer_repository':'Qwen/Qwen3-4B-Instruct-2507','tokenizer_revision':revision,
            'context_tokens':4096,'output_tokens':768,'temperature':0,'seed':28,'think':False}
        if expected.exists() and json.loads(expected.read_text('utf-8'))!=manifest:
            raise RuntimeError('Prepared model differs from pinned record; review deliberately before changing it')
        if not expected.exists(): expected.write_text(json.dumps(manifest,indent=2)+'\n','utf-8')
        (root/'prepared.json').write_text(json.dumps(manifest),'utf-8')
        print(json.dumps(manifest),flush=True)

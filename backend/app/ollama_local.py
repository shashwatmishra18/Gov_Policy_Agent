"""Project-owned local Ollama process; Windows job closes its complete runner tree."""
import ctypes
from ctypes import wintypes
import os
import shutil
from pathlib import Path
import subprocess
import time
import httpx

URL = 'http://127.0.0.1:11435'
TAG = 'qwen3:4b-instruct-2507-q4_K_M'


class WindowsJob:
    def __init__(self):
        k = ctypes.WinDLL('kernel32', use_last_error=True)
        k.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        k.CreateJobObjectW.restype = wintypes.HANDLE
        k.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        k.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        class Basic(ctypes.Structure):
            _fields_ = [('process_time',ctypes.c_int64),('job_time',ctypes.c_int64),('flags',wintypes.DWORD),
                ('min_working',ctypes.c_size_t),('max_working',ctypes.c_size_t),('process_limit',wintypes.DWORD),
                ('affinity',ctypes.c_size_t),('priority',wintypes.DWORD),('scheduling',wintypes.DWORD)]
        class Extended(ctypes.Structure):
            _fields_ = [('basic',Basic),('io',ctypes.c_uint64*6),('process_memory',ctypes.c_size_t),
                ('job_memory',ctypes.c_size_t),('peak_process',ctypes.c_size_t),('peak_job',ctypes.c_size_t)]
        self.kernel, self.handle = k, k.CreateJobObjectW(None,None)
        limits = Extended(); limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.handle or not k.SetInformationJobObject(self.handle,9,ctypes.byref(limits),ctypes.sizeof(limits)):
            self.close(); raise OSError('Cannot establish Ollama process containment')

    def assign(self, process):
        if not self.kernel.AssignProcessToJobObject(self.handle,int(process._handle)):
            process.kill(); self.close(); raise OSError('Cannot contain Ollama child')

    def close(self):
        if getattr(self,'handle',None): self.kernel.CloseHandle(self.handle); self.handle = None


class OllamaHost:
    def __init__(self, settings):
        self.root = settings.data_dir.parent/'ollama'
        self.cpu_only = settings.llm_cpu_only
        self.process = self.job = None

    def start(self):
        with httpx.Client(trust_env=False,timeout=0.5) as client:
            try: client.get(URL+'/api/version')
            except httpx.HTTPError: pass
            else: raise RuntimeError('Project Ollama port already occupied; stop the other project owner')
        binary = Path(os.environ['LOCALAPPDATA'])/'Programs/Ollama/ollama.exe' if os.name=='nt' else Path(shutil.which('ollama') or '/missing-ollama')
        if not binary.is_file(): raise RuntimeError('Pinned official Ollama installation required')
        self.root.mkdir(parents=True,exist_ok=True)
        env = os.environ.copy()
        env.update(OLLAMA_HOST='127.0.0.1:11435',OLLAMA_MODELS=str(self.root/'models'),
            OLLAMA_NO_CLOUD='1',OLLAMA_NOHISTORY='1',OLLAMA_NUM_PARALLEL='1',
            OLLAMA_MAX_LOADED_MODELS='1',OLLAMA_MAX_QUEUE='1',OLLAMA_CONTEXT_LENGTH='4096',
            OLLAMA_LOAD_TIMEOUT='60s',OLLAMA_KEEP_ALIVE='5m',OLLAMA_DEBUG='0')
        if self.cpu_only: env['CUDA_VISIBLE_DEVICES']='-1'
        from .processes import spawn_owned
        self.process,self.job = spawn_owned([str(binary),'serve'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(100):
            if self.process.poll() is not None: self.stop(); raise RuntimeError('Project Ollama failed to start')
            try:
                with httpx.Client(trust_env=False,timeout=0.5) as client:
                    response = client.get(URL+'/api/version'); response.raise_for_status()
                return
            except httpx.HTTPError: time.sleep(0.1)
        self.stop(); raise RuntimeError('Project Ollama startup deadline exceeded')

    def stop(self):
        if self.job: self.job.close(); self.job = None
        if self.process:
            self.process.wait(timeout=10); self.process = None

    def restart(self):
        self.stop(); self.start()

    def __enter__(self): self.start(); return self
    def __exit__(self,*args): self.stop()

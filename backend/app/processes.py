"""Contain trusted parser/model descendants using Windows jobs or supervised Linux sessions."""
import os
import signal
import subprocess
import sys
from pathlib import Path


class ProcessGroup:
    def __init__(self, process): self.pid = process.pid
    def close(self):
        if self.pid:
            try: os.killpg(self.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            self.pid = None


def spawn_owned(command, **kwargs):
    if os.name == 'nt':
        from .ollama_local import WindowsJob
        tree = WindowsJob()
        try:
            process = subprocess.Popen(command, creationflags=subprocess.CREATE_NO_WINDOW, **kwargs)
            tree.assign(process)
        except BaseException:
            if 'process' in locals() and process.poll() is None:process.kill();process.wait(timeout=10)
            tree.close(); raise
        return process, tree
    if sys.platform != 'linux': raise RuntimeError('Supported platforms: Windows and Linux')
    wrapper = Path(__file__).resolve().parents[1]/'process_guard.py'
    process = subprocess.Popen([sys.executable,str(wrapper),str(os.getpid()),*map(str,command)],
                               start_new_session=True, **kwargs)
    return process, ProcessGroup(process)


def install_shutdown():
    def stop(signum, frame): raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)

"""Linux supervisor: kill session descendants on parent death, including abrupt worker failure."""
import ctypes
import os
import signal
import subprocess
import sys

def terminate(signum, frame): os.killpg(os.getpid(), signal.SIGKILL)
signal.signal(signal.SIGTERM, terminate)
libc=ctypes.CDLL(None, use_errno=True)
if libc.prctl(1,signal.SIGTERM,0,0,0) != 0: raise OSError('Cannot establish parent-death containment')
if os.getppid()!=int(sys.argv[1]): terminate(None,None)
child=subprocess.Popen(sys.argv[2:])
try: sys.exit(child.wait())
except BaseException:
    if child.poll() is None: terminate(None,None)
    raise

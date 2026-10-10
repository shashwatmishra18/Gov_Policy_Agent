"""Private native supervisor. A stop marker closes only this service's contained tree."""
import json
from pathlib import Path
import subprocess
import sys
import time
from app.config import ROOT
from app.processes import spawn_owned
spec=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
process,tree=spawn_owned(spec['command'],cwd=spec['cwd'],stdout=sys.stdout,stderr=sys.stderr)
try:
    while process.poll() is None and not Path(spec['stop']).exists(): time.sleep(.2)
finally:
    tree.close()
    process.wait(timeout=10)

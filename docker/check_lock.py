"""Reject undeclared Linux transitives or version drift in the final installed environment."""
from importlib.metadata import distributions
from pathlib import Path
import re

def key(value):return re.sub(r'[-_.]+','-',value).lower()
expected={'pip':'26.2'}
for file in ('backend/requirements.lock','docker/requirements-linux.lock'):
    for line in Path(file).read_text().splitlines():
        if not line.strip() or line.startswith(('#','--')):continue
        match=re.fullmatch(r'([A-Za-z0-9_.-]+)==([^\s;]+)',line.strip())
        if not match:raise SystemExit('Unsupported dependency lock entry')
        expected[key(match[1])]=match[2]
actual={key(d.metadata['Name']):d.version for d in distributions()}
if actual!=expected:raise SystemExit('Installed Linux dependency set differs from the declared locks')
print('Exact installed Linux dependency set matches shared and Linux locks.')

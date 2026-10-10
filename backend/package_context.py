"""Assemble an allowlisted, private-asset-free build context, including on OneDrive/Windows."""
from pathlib import Path
import os
import shutil
from app.config import ROOT
target=ROOT/'runtime/package-context'
if target.exists():
    if target.resolve().parent != (ROOT/'runtime').resolve() or target.is_symlink(): raise SystemExit('Unsafe context target')
    shutil.rmtree(target)
target.mkdir(parents=True)
paths=[ROOT/'.dockerignore',ROOT/'docs/llm_model.json',ROOT/'docs/SOURCES.md']
paths.extend(path for name in ('LICENSE','NOTICE') if (path:=ROOT/name).is_file())
paths.extend(ROOT/'docker/licenses'/name for name in ('tesseract-LICENSE','ollama-LICENSE'))
for folder,extensions in [('backend',{'.py','.ini','.in','.lock','.mako'}),('docker',{'.py','.sh','.conf','.yaml','.Dockerfile','.example','.lock'}),('frontend/src',{'.ts','.tsx','.css'})]:
    for parent,dirs,files in os.walk(ROOT/folder):
        dirs[:]=[d for d in dirs if d not in ('__pycache__','node_modules','.git','runtime','models')]
        paths.extend(Path(parent)/f for f in files if Path(f).suffix in extensions)
paths.extend(ROOT/'frontend'/n for n in ('package.json','package-lock.json','index.html','tsconfig.json','tsconfig.app.json','tsconfig.node.json','vite.config.ts') if (ROOT/'frontend'/n).exists())
for path in paths:
    if path.is_symlink():raise SystemExit('Symlink source rejected')
    output=target/path.relative_to(ROOT);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(path.read_bytes().replace(b'\r\n',b'\n'))
print('Source-only build context assembled; no native configuration, models, corpus or runtime included.')

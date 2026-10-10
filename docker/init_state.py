from pathlib import Path
import os
for name in ('data','models','ollama','ocr','vectors','locks'):
    p=Path('/state')/name;p.mkdir(parents=True,exist_ok=True);os.chown(p,10001,10001)

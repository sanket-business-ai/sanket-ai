import importlib.util
import subprocess
import sys
from pathlib import Path

print('Python:', sys.executable)
for module in ('pypdf', 'fastapi', 'pandas', 'sqlalchemy', 'httpx', 'pytest'):
    print(module, bool(importlib.util.find_spec(module)))
for parent in Path.cwd().parents:
    instructions = parent / 'AGENTS.md'
    if instructions.exists():
        print(instructions, instructions.read_text())
try:
    from pypdf import PdfReader
    print('\n'.join(page.extract_text() for page in PdfReader('idea.pdf').pages))
except ImportError:
    print('PDF reader not installed')

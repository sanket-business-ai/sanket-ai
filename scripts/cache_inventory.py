import json
import zipfile
from pathlib import Path

cache = Path.home() / 'AppData/Local/pip/Cache/http-v2'
found = {}
for path in cache.rglob('*.body'):
    try:
        with zipfile.ZipFile(path) as wheel:
            metadata = next((n for n in wheel.namelist() if n.endswith('.dist-info/METADATA')), None)
            if metadata:
                text = wheel.read(metadata).decode()
                name = next(line[6:] for line in text.splitlines() if line.startswith('Name: '))
                version = next(line[9:] for line in text.splitlines() if line.startswith('Version: '))
                found[name] = version
    except (OSError, zipfile.BadZipFile):
        pass
print(json.dumps(found, indent=2))

"""Copy compatible, already downloaded wheels into a workspace-local wheelhouse."""
import shutil
import zipfile
from pathlib import Path
from pip._vendor.packaging.tags import parse_tag, sys_tags

supported = set(sys_tags())
destination = Path('.cache/wheels')
destination.mkdir(parents=True, exist_ok=True)
for path in (Path.home() / 'AppData/Local/pip/Cache/http-v2').rglob('*.body'):
    try:
        with zipfile.ZipFile(path) as wheel:
            info = next((n for n in wheel.namelist() if n.endswith('.dist-info/WHEEL')), None)
            if not info:
                continue
            tags = [line[5:] for line in wheel.read(info).decode().splitlines() if line.startswith('Tag: ')]
            tag = next((tag for tag in tags if supported & parse_tag(tag)), None)
            if tag:
                filename = info.split('/')[0].removesuffix('.dist-info') + '-' + tag + '.whl'
                shutil.copyfile(path, destination / filename)
    except (OSError, zipfile.BadZipFile):
        pass
print(f'Recovered {len(list(destination.glob("*.whl")))} compatible wheels')

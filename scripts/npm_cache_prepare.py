import base64
import json
import tarfile
from pathlib import Path

source = Path.home() / 'AppData/Local/npm-cache/_cacache/content-v2'
packages = {}
for entry in json.loads(Path('.cache/npm-entries.json').read_text()):
    integrity = entry['integrity'].split()[0]
    algorithm, digest = integrity.split('-', 1)
    digest = base64.b64decode(digest).hex()
    path = source / algorithm / digest[:2] / digest[2:4] / digest[4:]
    try:
        with tarfile.open(path, 'r:gz') as archive:
            manifest_path = next((name for name in archive.getnames() if name.count('/') == 1 and name.endswith('/package.json')), None)
            if not manifest_path:
                continue
            manifest = json.load(archive.extractfile(manifest_path))
        manifest['dist'] = {'tarball': entry['key'].split('request-cache:', 1)[1], 'integrity': entry['integrity']}
        packages.setdefault(manifest['name'], {})[manifest['version']] = manifest
    except (OSError, KeyError, tarfile.TarError):
        pass
needed = set()
pending = list(json.loads(Path('frontend/package.json').read_text())['dependencies']) + list(json.loads(Path('frontend/package.json').read_text())['devDependencies']) + ['skills']
while pending:
    name = pending.pop()
    if name in needed:
        continue
    needed.add(name)
    for version in packages.get(name, {}).values():
        pending.extend(version.get('dependencies', {}))
        pending.extend(version.get('optionalDependencies', {}))
        pending.extend(version.get('peerDependencies', {}))
Path('.cache/npm-packages.json').write_text(json.dumps({k: v for k, v in packages.items() if k in needed}))
Path('.cache/npm-needed.json').write_text(json.dumps(sorted(needed)))

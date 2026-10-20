"""Export the synthetic evidence pack for inspection or manual uploads."""
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'backend'))
from app.demo import demo_pack

for pack, folder in [('supply', 'himalayanmart'), ('margin', 'himalayanmart_margin')]:
    directory = root / 'backend/datasets' / folder
    directory.mkdir(parents=True, exist_ok=True)
    files = demo_pack(pack)
    for kind, name, data in files:
        (directory / name).write_bytes(data)
    print(f'Exported {len(files)} synthetic {pack} evidence files to {directory}')

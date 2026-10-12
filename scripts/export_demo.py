"""Export the synthetic evidence pack for inspection or manual uploads."""
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'backend'))
from app.demo import demo_pack

directory = root / 'backend/datasets/himalayanmart'
directory.mkdir(parents=True, exist_ok=True)
for kind, name, data in demo_pack():
    (directory / name).write_bytes(data)
print(f'Exported 12 synthetic evidence files to {directory}')

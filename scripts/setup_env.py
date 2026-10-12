"""Create local development secrets once; existing configuration is preserved."""
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / '.env'
if target.exists():
    print('Existing .env preserved.')
else:
    template = (root / '.env.example').read_text()
    template = template.replace('SANKET_ADMIN_PASSWORD=replace-with-a-long-random-password', 'SANKET_ADMIN_PASSWORD=' + secrets.token_urlsafe(24))
    template = template.replace('POSTGRES_PASSWORD=replace-with-a-long-random-password', 'POSTGRES_PASSWORD=' + secrets.token_urlsafe(24))
    target.write_text(template)
    print('Created .env with generated secrets. Read the local file for your administrator password.')

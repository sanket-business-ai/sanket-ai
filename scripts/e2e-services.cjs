const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
fs.mkdirSync(path.join(root, '.cache'), { recursive: true });
const python = process.env.E2E_PYTHON || path.join(root, process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python');
const env = { ...process.env, SANKET_ADMIN_EMAIL: 'founder@sanketai.local', SANKET_ADMIN_PASSWORD: 'e2e-only-password-12345', SANKET_AGENT_MODE: 'deterministic', SANKET_DATABASE_URL: `sqlite:///${path.join(root, '.cache', `e2e-${Date.now()}.db`).replaceAll('\\', '/')}`, SANKET_FRONTEND_ORIGIN: 'http://127.0.0.1:5174', SANKET_ENVIRONMENT: 'development' };
const api = spawn(python, ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8011'], { cwd: path.join(root, 'backend'), env, stdio: 'inherit', windowsHide: true });
let worker;
const ready = setInterval(async () => {
  try {
    if ((await fetch('http://127.0.0.1:8011/api/health')).ok) {
      clearInterval(ready);
      worker = spawn(python, ['-m', 'app.worker'], { cwd: path.join(root, 'backend'), env, stdio: 'inherit', windowsHide: true });
    }
  } catch { /* Wait for the API to migrate the test database. */ }
}, 500);
const stop = () => { clearInterval(ready); api.kill(); worker?.kill(); };
process.on('SIGINT', stop);
process.on('SIGTERM', stop);
process.on('exit', stop);
api.on('exit', code => { worker?.kill(); process.exit(code ?? 0); });

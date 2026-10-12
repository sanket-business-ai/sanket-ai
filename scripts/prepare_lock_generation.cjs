const fs = require('node:fs');
fs.mkdirSync('.cache/lock-generation/frontend', { recursive: true });
fs.copyFileSync('package.json', '.cache/lock-generation/package.json');
fs.copyFileSync('frontend/package.json', '.cache/lock-generation/frontend/package.json');

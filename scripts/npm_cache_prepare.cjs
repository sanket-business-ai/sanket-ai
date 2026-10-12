// Reconstruct registry metadata from locally cached tarballs; never uses the network.
const cacache = require('C:/Program Files/nodejs/node_modules/npm/node_modules/cacache');
const fs = require('node:fs');
const cp = require('node:child_process');
(async () => {
  const source = 'C:/Users/Prasanna/AppData/Local/npm-cache/_cacache';
  const entries = await cacache.ls(source);
  fs.mkdirSync('.cache', { recursive: true });
  fs.writeFileSync('.cache/npm-entries.json', JSON.stringify(Object.values(entries).filter(e => e.key.includes('registry.npmjs.org/') && e.key.endsWith('.tgz'))));
  cp.execFileSync('python', ['scripts/npm_cache_prepare.py'], { stdio: 'inherit' });
  const packages = JSON.parse(fs.readFileSync('.cache/npm-packages.json'));
  const target = '.cache/npm/_cacache';
  const needed = new Set(JSON.parse(fs.readFileSync('.cache/npm-needed.json')));
  for (const entry of Object.values(entries)) {
    if (entry.key.includes('registry.npmjs.org/') && !entry.key.endsWith('.tgz')) {
      const name = decodeURIComponent(entry.key.split('registry.npmjs.org/')[1]);
      if (needed.has(name) && !packages[name]) {
        await cacache.put(target, entry.key, await cacache.get.stream(source, entry.key).concat(), { metadata: entry.metadata });
      }
    }
  }
  for (const [name, versions] of Object.entries(packages)) {
    for (const value of Object.values(versions)) {
      const key = `make-fetch-happen:request-cache:${value.dist.tarball}`;
      const entry = entries[key];
      await cacache.put(target, key, await cacache.get.stream(source, key).concat(), { metadata: entry.metadata });
    }
    const url = 'https://registry.npmjs.org/' + name.replace('/', '%2f');
    const data = { name, 'dist-tags': { latest: Object.keys(versions).at(-1) }, versions };
    for (const accept of ['application/json', 'application/vnd.npm.install-v1+json']) {
      await cacache.put(target, `make-fetch-happen:request-cache:${url}`, JSON.stringify(data), { metadata: { time: Date.now(), url, reqHeaders: { accept }, resHeaders: { 'content-type': 'application/json', 'cache-control': 'public, max-age=31536000' }, options: { compress: true } } });
    }
  }
  console.log('Prepared offline cache:', Object.keys(packages).length, 'packages');
})();

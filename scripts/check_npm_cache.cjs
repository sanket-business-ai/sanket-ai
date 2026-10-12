const cacache = require('C:/Program Files/nodejs/node_modules/npm/node_modules/cacache');
(async () => {
  const fs = require('node:fs');
  console.log(fs.readFileSync('C:/Program Files/nodejs/node_modules/npm/node_modules/make-fetch-happen/lib/cache/policy.js', 'utf8'));
  const entries = await cacache.ls('.cache/npm/_cacache');
  console.log(Object.keys(entries).filter(k => k.includes('playwright')));
  console.log(await cacache.get.info('.cache/npm/_cacache', 'make-fetch-happen:request-cache:https://registry.npmjs.org/@playwright%2ftest'));
})();

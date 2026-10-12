const cacache = require('C:/Program Files/nodejs/node_modules/npm/node_modules/cacache');
(async () => { const entries = await cacache.ls('C:/Users/Prasanna/AppData/Local/npm-cache/_cacache'); console.log(Object.keys(entries).filter(k => k.includes('/prettier/-/'))); })();

const cacache = require('C:/Program Files/nodejs/node_modules/npm/node_modules/cacache');
const names = ['react', 'react-dom', 'vite', '@vitejs/plugin-react', 'typescript', 'tailwindcss', '@tailwindcss/vite', 'lucide-react', '@radix-ui/react-dialog', '@radix-ui/react-slot', '@radix-ui/react-tabs', 'class-variance-authority', 'clsx', 'tailwind-merge', '@tanstack/react-query', 'react-router-dom', 'recharts', 'vitest', '@testing-library/react', '@playwright/test', 'skills'];
(async () => {
  const entries = await cacache.ls('C:/Users/Prasanna/AppData/Local/npm-cache/_cacache');
  for (const name of names) {
    const prefix = `make-fetch-happen:request-cache:https://registry.npmjs.org/${name}/-/`;
    console.log(name, Object.keys(entries).filter(key => key.startsWith(prefix)).map(key => key.split('/').pop()).join(', '));
  }
})();

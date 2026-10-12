const fs = require('node:fs');
const path = 'frontend/src/pages/Actions.tsx';
const text = fs.readFileSync(path, 'utf8');
fs.writeFileSync(path, text.replace('Follow-ups are checked when you select “Check outcome.”', 'The worker checks approved tasks when their follow-up is due. You can also select “Check outcome” at any time. Missing outcome data defers the scheduled check by one day.'));

import { chromium } from 'playwright-core';
import path from 'node:path';
const root = path.resolve('.');
const b = await chromium.launch({ channel: 'chrome' });
const p = await b.newPage({ viewport: { width: 384, height: 688 }, deviceScaleFactor: 2 });
await p.goto('file://' + path.join(root, 'index.html'));
const a = await p.$('a.cta');
const box = await a.boundingBox();
console.log('CTA href :', await a.getAttribute('href'));
console.log('CTA box  :', JSON.stringify(box));
console.log('tap target:', box.width.toFixed(0) + 'x' + box.height.toFixed(0),
            '(WCAG 2.2 minimum is 24x24)');
// confirm a click actually tries to navigate there
let nav = null;
p.on('framenavigated', f => { if (f === p.mainFrame()) nav = f.url(); });
await p.evaluate(() => {
  document.querySelector('a.cta').addEventListener('click', e => {
    e.preventDefault();
    window.__target = e.currentTarget.href;
  });
});
await a.click();
console.log('click resolves to:', await p.evaluate(() => window.__target));
await b.close();

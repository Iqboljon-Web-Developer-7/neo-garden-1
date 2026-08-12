import { chromium } from 'playwright-core';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const b = await chromium.launch({ channel: 'chrome' });
const p = await b.newPage({ viewport: { width: 384, height: 688 }, deviceScaleFactor: 2 });
await p.goto('file://' + path.join(root, 'index.html') + '?freeze=01:51');
console.log(JSON.stringify(await p.evaluate(() => {
  const t = document.querySelector('.timer').getBoundingClientRect();
  return { w: +t.width.toFixed(2), h: +t.height.toFixed(2), top: +t.top.toFixed(2), left: +t.left.toFixed(2) };
}), null, 1));
await b.close();

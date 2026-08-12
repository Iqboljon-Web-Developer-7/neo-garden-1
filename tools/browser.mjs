import { chromium } from 'playwright-core';
import { existsSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';

const CANDIDATES = [
  join(homedir(), 'Library/Caches/ms-playwright/chromium-1228/chrome-mac/Chromium.app/Contents/MacOS/Chromium'),
  join(homedir(), 'Library/Caches/ms-playwright/chromium_headless_shell-1228/chrome-headless-shell-mac-x64/chrome-headless-shell'),
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
];

export function chromePath() {
  const hit = CANDIDATES.find(existsSync);
  if (!hit) throw new Error('No Chromium found. Tried:\n' + CANDIDATES.join('\n'));
  return hit;
}

export function launch(opts = {}) {
  return chromium.launch({ executablePath: chromePath(), ...opts });
}

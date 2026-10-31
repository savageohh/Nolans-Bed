const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const pg = await b.newPage({ viewport: { width: 1200, height: 900 } });
  
  pg.on('pageerror', e => console.log('err:', e.message));
  const path = require('path'); const root = path.join(__dirname, '..');
  const base = 'file://' + path.join(root, 'viewer/index.html');
  for (const [name, q] of [['iso','view=iso&ui=0'],['exploded','view=iso&explode=1&ui=0&mattress=0'],['front','view=front&ui=0&mattress=0'],['end','view=end&ui=0&mattress=0'],['viewer','view=iso']]) {
    await pg.goto(base + '?' + q);
    await pg.waitForFunction(() => window.__ready, null, { timeout: 30000 });
    await pg.waitForTimeout(800);
    await pg.screenshot({ path: path.join(root, 'docs/img', name) + '.png' });
  }
  await b.close();
})();

// Renders Lucide SVGs as white glyphs on coloured rounded squares (PNG, transparent corners).
const { chromium } = require('playwright');
const fs = require('fs');
const [src, out] = process.argv.slice(2);
const icons = [
  ['video', 'film', '#D95757'],
  ['audio', 'volume-2', '#4B69D9'],
  ['gallery', 'image', '#E8914F'],
  ['file', 'file-text', '#55A072'],
];
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 120, height: 120 }, deviceScaleFactor: 1 });
  for (const [name, lucide, color] of icons) {
    const svg = fs.readFileSync(`${src}/${lucide}.svg`, 'utf8').replace(/<!--[\s\S]*?-->/, '');
    await p.setContent(`<html><body style="margin:0;background:transparent">
      <div style="width:120px;height:120px;border-radius:27px;background:${color};color:#fff;display:flex;align-items:center;justify-content:center">
      ${svg.replace('width="24"', 'width="62"').replace('height="24"', 'height="62"')}</div></body></html>`);
    await p.screenshot({ path: `${out}/${name}.png`, omitBackground: true });
  }
  await p.setViewportSize({ width: 580, height: 160 });
  const imgs = icons.map(([n]) => `<img src="data:image/png;base64,${fs.readFileSync(`${out}/${n}.png`).toString('base64')}" style="margin:20px 10px">`).join('');
  await p.setContent(`<html><body style="margin:0;background:#1c1c1e;padding-left:10px">${imgs}</body></html>`);
  await p.screenshot({ path: process.argv[4] });
  await b.close();
})();

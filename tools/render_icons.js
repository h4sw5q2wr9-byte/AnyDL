// Renders Lucide icons (https://lucide.dev, ISC license) as white glyphs on
// coloured rounded squares, the style of the AnyDL menus.
// Usage: node tools/render_icons.js <lucide icons folder> <output folder> [preview.png]
const { chromium } = require('playwright');
const fs = require('fs');
const [src, out, preview] = process.argv.slice(2);
const RED = '#D95757', BLUE = '#4B69D9', ORANGE = '#E8914F', GREEN = '#55A072', PURPLE = '#8E5BD9',
      TEAL = '#3AA6B9', GRAY = '#8E8E93', YELLOW = '#D9A928', PINK = '#D9578E', INDIGO = '#5856D6',
      CRIMSON = '#D64541', SKY = '#3A8FD9';
// [file name, Lucide icon, colour]
const icons = [
  // main menu
  ['video', 'film', RED], ['audio', 'volume-2', BLUE], ['gallery', 'image', ORANGE],
  ['file', 'file-text', GREEN], ['tools', 'wand-sparkles', PURPLE], ['library', 'folder-open', TEAL],
  ['settings', 'settings', GRAY],
  // media tools
  ['compress', 'shrink', PURPLE], ['trim', 'scissors', PINK], ['gif', 'image-play', ORANGE],
  ['extract', 'audio-lines', BLUE], ['convert', 'arrow-left-right', GREEN], ['back', 'arrow-left', GRAY],
  // my downloads
  ['music', 'music', BLUE], ['photos', 'images', ORANGE], ['playlists', 'list-video', PURPLE],
  ['recent', 'history', YELLOW],
  // settings
  ['quality', 'monitor-play', RED], ['fps', 'gauge', ORANGE], ['codec', 'clapperboard', INDIGO],
  ['subtitles', 'captions', GREEN], ['after', 'download', TEAL], ['keep', 'clock', YELLOW],
  ['clear', 'trash-2', CRIMSON], ['updates', 'refresh-cw', SKY], ['help', 'circle-help', GRAY],
  ['signin', 'key-round', PINK],
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
  if (preview) {
    const cols = 7, cell = 140;
    await p.setViewportSize({ width: cols * cell + 20, height: Math.ceil(icons.length / cols) * cell + 20 });
    const imgs = icons.map(([n]) => `<img src="data:image/png;base64,${fs.readFileSync(`${out}/${n}.png`).toString('base64')}" style="margin:10px">`).join('');
    await p.setContent(`<html><body style="margin:0;padding:10px;background:#1c1c1e;width:${cols * cell}px">${imgs}</body></html>`);
    await p.screenshot({ path: preview });
  }
  await b.close();
})();

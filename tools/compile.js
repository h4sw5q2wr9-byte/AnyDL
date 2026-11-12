// Usage: node compile.js <source.cherri> <out.shortcut>   (unsigned build via the playground)
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const src = fs.readFileSync(process.argv[2], 'utf8');
  const b = await chromium.launch();
  const p = await b.newPage();
  await p.goto('https://playground.cherrilang.org/', { waitUntil: 'networkidle', timeout: 60000 });
  const res = await p.evaluate(async (content) => {
    const m = document.cookie.match(/XSRF-TOKEN=([^;]+)/);
    const r = await fetch('/compile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest', 'X-XSRF-TOKEN': m ? decodeURIComponent(m[1]) : '' },
      body: JSON.stringify({ active_file: { id: 'file-1', name: 'main.cherri', content, compiled: false, error: null, output: null, decompOutput: null, shareLink: null }, files: [] }),
    });
    return { status: r.status, text: await r.text() };
  }, src);
  console.log(res.status, res.text.slice(0, 3000));
  try {
    const j = JSON.parse(res.text);
    if (j.file) {
      const u = j.file.replace(/ /g, '%20');
      let ok = false;
      for (let i = 0; i < 5 && !ok; i++) {
        const r = await p.request.get(u);
        const body = await r.body();
        console.log('GET', r.status(), r.headers()['content-type'], body.length);
        if (r.status() === 200) { fs.writeFileSync(process.argv[3], body); console.log('saved', process.argv[3]); ok = true; }
        else await p.waitForTimeout(2000);
      }
      if (!ok) process.exitCode = 1;
    }
  } catch (e) { console.log('ERR', e.message); }
  await b.close();
})();

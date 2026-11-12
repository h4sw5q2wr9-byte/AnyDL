// Usage: node sign.js <unsigned.shortcut> <name> <signed-out.shortcut>   (signs via the playground's HubSign route)
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const data = fs.readFileSync(process.argv[2], 'utf8');
  const name = process.argv[3];
  const b = await chromium.launch();
  const p = await b.newPage();
  await p.goto('https://playground.cherrilang.org/', { waitUntil: 'networkidle', timeout: 60000 });
  const res = await p.evaluate(async ({ name, data }) => {
    const m = document.cookie.match(/XSRF-TOKEN=([^;]+)/);
    const r = await fetch('/sign', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest', 'X-XSRF-TOKEN': m ? decodeURIComponent(m[1]) : '' },
      body: JSON.stringify({ name, data }),
    });
    return { status: r.status, text: await r.text() };
  }, { name, data });
  console.log('SIGN', res.status, res.text.slice(0, 300));
  if (res.status === 200 && res.text.trim().startsWith('/')) {
    const u = 'https://playground.cherrilang.org' + encodeURI(res.text.trim());
    const r = await p.request.get(u);
    const body = await r.body();
    console.log('GET', r.status(), body.length, JSON.stringify(body.slice(0, 4).toString('latin1')));
    if (r.status() === 200) { fs.writeFileSync(process.argv[4], body); console.log('saved', process.argv[4]); }
    else process.exitCode = 1;
  } else process.exitCode = 1;
  await b.close();
})();

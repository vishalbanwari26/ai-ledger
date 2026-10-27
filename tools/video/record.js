// Records the live demo with Playwright and logs when each narration segment starts.
// Usage: NEBIUS_API_KEY=... node tools/video/record.js   (writes video/rec/*.webm, video/marks.json, video/intro.png, video/outro.png)
const { chromium } = require(process.env.PLAYWRIGHT || '/Users/vishalbanwari/.npm/_npx/e41f203b7505f1fb/node_modules/playwright');
const fs = require('fs'), path = require('path');
const ROOT = path.resolve(__dirname, '..', '..'), OUT = path.join(ROOT, 'video');
const BASE = process.env.BASE || 'https://vishalbanwari.tech/ai-ledger/';
const dur = Object.fromEntries(JSON.parse(fs.readFileSync(path.join(OUT, 'durations.json'))).map(s => [s.id, s.dur * 1000]));
const sleep = ms => new Promise(r => setTimeout(r, ms));
const GAP = 450;

(async () => {
  fs.rmSync(path.join(OUT, 'rec'), { recursive: true, force: true });
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1067, height: 600 }, deviceScaleFactor: 1.2, recordVideo: { dir: path.join(OUT, 'rec'), size: { width: 1280, height: 720 } } });
  await ctx.addInitScript(k => {
    try { if (k) localStorage.setItem('ail_key', k); } catch (e) {}
    window.addEventListener('DOMContentLoaded', () => {   // a visible cursor and click feedback, since video capture hides the real one
      const c = document.createElement('div');
      c.style.cssText = 'position:fixed;z-index:99999;width:20px;height:20px;border:2px solid #fff;border-radius:50%;background:rgba(110,168,254,.5);pointer-events:none;transform:translate(-50%,-50%);left:-60px;top:-60px;transition:transform .1s,background .1s';
      document.body.appendChild(c);
      document.addEventListener('mousemove', e => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; }, true);
      document.addEventListener('mousedown', () => { c.style.transform = 'translate(-50%,-50%) scale(.55)'; c.style.background = 'rgba(74,222,128,.7)'; }, true);
      document.addEventListener('mouseup', () => { c.style.transform = 'translate(-50%,-50%) scale(1)'; c.style.background = 'rgba(110,168,254,.5)'; }, true);
    });
  }, process.env.NEBIUS_API_KEY || '');
  const t0 = Date.now(); const page = await ctx.newPage(); const T = () => Date.now() - t0;
  page.on('pageerror', e => console.log('PAGEERROR', String(e).slice(0, 160)));
  const marks = {};

  const center = async sel => { const b = await page.locator(sel).first().boundingBox(); return b && { x: b.x + b.width / 2, y: b.y + b.height / 2, b }; };
  const move = async (sel, dx = 0, dy = 0) => { const c = await center(sel); if (c) await page.mouse.move(c.x + dx, c.y + dy, { steps: 28 }); };
  const ensureVisible = async sel => { const need = await page.$eval(sel, e => { const r = e.getBoundingClientRect(); return r.top < 70 || r.bottom > window.innerHeight - 30; }); if (need) { await page.$eval(sel, e => e.scrollIntoView({ behavior: 'smooth', block: 'center' })); await sleep(900); } };
  const click = async sel => { await ensureVisible(sel); await move(sel); await sleep(250); await page.mouse.down(); await sleep(90); await page.mouse.up(); await sleep(150); };
  const scrollTo = async (sel, block = 'start') => { await page.evaluate(([s, b]) => document.querySelector(s).scrollIntoView({ behavior: 'smooth', block: b }), [sel, block]); await sleep(1100); };
  const tab = async t => { await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' })); await sleep(650); await click(`#tabs button[data-tab=${t}]`); await sleep(300); };
  const type = async (sel, text) => { await click(sel); await page.keyboard.type(text, { delay: 32 }); };
  const seg = async (id, fn) => { console.log('segment', id, (T() / 1000).toFixed(1) + 's'); marks[id] = T(); await Promise.all([fn(), sleep(dur[id] + GAP)]); };

  await page.goto(BASE);
  await page.waitForFunction(() => { const e = document.getElementById('o1'); return e && e.textContent.includes('$') && document.querySelector('#c-forest svg'); }, null, { timeout: 120000 });
  await sleep(500); const trim = T();

  await seg('s1', async () => {
    await sleep(900); await move('#o1', 0, 20); await sleep(5200);
    await move('#o2', 0, 20); await sleep(6200);
    await move('#o3', 0, 20); await sleep(5200);
    await scrollTo('#c-forest', 'center'); await sleep(800);
    const c = await center('#c-forest'); if (c) await page.mouse.move(c.x + 60, c.y - 40, { steps: 30 }); await sleep(2500);
  });
  await tab('waste'); await sleep(300);
  await seg('s2', async () => {
    const c = await center('#c-split svg'); if (c) { await page.mouse.move(c.b.x + c.b.width * 0.55, c.y - 8, { steps: 30 }); }
    await sleep(4500); await scrollTo('#waste', 'start'); await sleep(2500);
    await move('#waste tr:nth-child(2) td:last-child'); await sleep(1000);
  });
  await seg('s3', async () => {
    await scrollTo('#acts', 'start'); await sleep(500);
    const boxes = await page.$$eval('#acts tr', rows => rows.map((r, i) => ({ i, t: r.innerText.toLowerCase().includes('reassign unused seats') })).filter(x => x.t).slice(0, 2).map(x => x.i));
    for (const i of boxes) { await click(`#acts tr:nth-child(${i + 1}) .ak`); await sleep(500); }
    await scrollTo('#actsum', 'center'); await sleep(500);
  });
  await tab('real'); await sleep(300);
  await seg('s4', async () => {
    const c = await center('#c-index svg'); if (c) { await page.mouse.move(c.b.x + c.b.width * 0.35, c.y, { steps: 30 }); await sleep(1800); await page.mouse.move(c.b.x + c.b.width * 0.78, c.y - 20, { steps: 30 }); }
    await sleep(5500); await scrollTo('#depts', 'start'); await sleep(2500);
    await move('#depts tr:nth-child(4) td:nth-child(5)'); await sleep(1500);
  });
  await tab('evidence'); await scrollTo('#c-evidence', 'start'); await sleep(300);
  await seg('s5', async () => {
    const c = await center('#c-evidence svg'); if (c) await page.mouse.move(c.b.x + c.b.width * 0.5, c.b.y + 60, { steps: 30 });
    await sleep(3000); await move('#becard', 0, 0);
  });
  await tab('budget'); await sleep(300);
  await seg('s6', async () => {
    const dots = await page.$$eval('#c-trade circle[tabindex]', cs => cs.map(c => { const r = c.getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 }; }));
    dots.sort((a, b) => a.x - b.x);
    for (const d of dots) { await page.mouse.move(d.x, d.y, { steps: 24 }); await sleep(2300); }
  });
  await tab('value'); await scrollTo('#vtab', 'start'); await sleep(300);
  await seg('s6b', async () => {
    await sleep(1800);
    await tab('rules'); await sleep(500); await move('#rulebox [data-rule=high_spend_mult]'); await sleep(2500);
  });
  await tab('ask'); await scrollTo('#q', 'center'); await sleep(300);
  await seg('s7a', async () => {
    await type('#q', 'Which department has the most unused seats, and how much is that worth a month?');
    await sleep(400); await click('#ab');
  });
  await page.waitForFunction(() => { const a = document.getElementById('ans').textContent; return a && !a.startsWith('Thinking') && a.length > 40; }, null, { timeout: 60000 })
    .catch(async e => { console.log('LIVE ASK DID NOT ANSWER. ans=', JSON.stringify(await page.$eval('#ans', x => x.textContent)), 'err=', JSON.stringify(await page.$eval('#aerr', x => x.textContent)), 'key set=', await page.evaluate(() => !!localStorage.getItem('ail_key'))); throw e; });
  await seg('s7b', async () => {
    await scrollTo('#ans', 'start'); await sleep(2500);
    await click('#evd summary'); await sleep(800); await page.mouse.wheel(0, 260); await sleep(2200);
    await scrollTo('#ans', 'start');
  });
  await seg('s8a', async () => {
    await click('#q'); await page.keyboard.press('Meta+A'); await page.keyboard.press('Backspace');
    await page.keyboard.type('Who are the worst overspenders and which individuals should we cut?', { delay: 24 });
    await sleep(300); await click('#ab');
  });
  await page.waitForFunction(() => document.getElementById('ans').textContent.includes('does not identify'), null, { timeout: 120000 });
  await seg('s8b', async () => { await scrollTo('#ans', 'start'); await sleep(500); await move('#ans', -120, 10); await sleep(3000); });
  await sleep(600);
  const total = T();

  // title and end cards
  const card = (title, lines) => `<body style="margin:0;width:1280px;height:720px;background:#0e1116;color:#e6e9ee;font-family:-apple-system,Helvetica,Arial,sans-serif;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center">
    <div style="font-size:84px;font-weight:700;letter-spacing:-1px">${title}</div>${lines.map(l => `<div style="font-size:34px;color:#8b95a5;margin-top:22px">${l}</div>`).join('')}</body>`;
  const cp = await (await browser.newContext({ viewport: { width: 1280, height: 720 } })).newPage();
  await cp.setContent(card('AI Ledger', ['Is your AI spend paying off?', 'NVIDIA Nemotron on Nebius Token Factory'])); await cp.screenshot({ path: path.join(OUT, 'intro.png') });
  await cp.setContent(card('AI Ledger', ['vishalbanwari.tech/ai-ledger', 'github.com/vishalbanwari26/ai-ledger', 'Open source, MIT licence']).replace('font-size:34px;color:#8b95a5;margin-top:22px">vishalbanwari', 'font-size:44px;color:#6ea8fe;margin-top:30px">vishalbanwari')); await cp.screenshot({ path: path.join(OUT, 'outro.png') });

  const video = await page.video().path();
  await ctx.close(); await browser.close();
  fs.writeFileSync(path.join(OUT, 'marks.json'), JSON.stringify({ trim, marks, total, video }, null, 1));
  console.log('recorded', (total / 1000).toFixed(1) + 's of screen, trim', (trim / 1000).toFixed(1) + 's ->', video);
})().catch(e => { console.log('CRASH', e.message); process.exit(2); });

#!/usr/bin/env node
// qa: render the PPTX with PowerPoint (macOS) or LibreOffice, compare each slide with the HTML reference
// screenshot taken during conversion, rank slides by visual difference and write side-by-side sheets.
// Usage: node qa.mjs out.pptx [--work DIR] [--renderer powerpoint|libreoffice] [--per-sheet 4] [--width 560]
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { parseArgs } from 'node:util';
import { chromium } from 'playwright';

const { values: a, positionals } = parseArgs({ allowPositionals: true, options: { work: { type: 'string' }, renderer: { type: 'string' }, 'per-sheet': { type: 'string' }, width: { type: 'string' }, browser: { type: 'string' } } });
const pptx = path.resolve(positionals[0] || '');
if (!positionals[0] || !fs.existsSync(pptx)) { console.error('usage: qa.mjs out.pptx [--work DIR] [--renderer powerpoint|libreoffice]'); process.exit(2); }
const work = path.resolve(a.work || pptx.replace(/\.pptx$/i, '') + '.work');
const qa = path.join(work, 'qa'); fs.rmSync(qa, { recursive: true, force: true }); fs.mkdirSync(qa, { recursive: true });
const manifest = JSON.parse(fs.readFileSync(path.join(work, 'manifest.json'), 'utf8'));
const which = b => { try { execFileSync('which', [b], { stdio: 'ignore' }); return true; } catch { return false; } };
const hasPowerPoint = process.platform === 'darwin' && fs.existsSync('/Applications/Microsoft PowerPoint.app');
const renderer = a.renderer || (hasPowerPoint ? 'powerpoint' : 'libreoffice');

// 1. PPTX -> PDF
const tmp = process.platform === 'darwin' ? '/tmp' : os.tmpdir();
const tp = path.join(tmp, `h2p-qa-${process.pid}.pptx`), pdf = tp.replace(/\.pptx$/, '.pdf');
fs.copyFileSync(pptx, tp);
if (renderer === 'powerpoint') {
  execFileSync('osascript', ['-e', `tell application "Microsoft PowerPoint"
  open POSIX file "${tp}"
  delay 3
  set p to active presentation
  save p in POSIX file "${pdf}" as save as PDF
  close p saving no
end tell`], { stdio: 'inherit', timeout: 600000 });
} else {
  const so = which('soffice') ? 'soffice' : '/Applications/LibreOffice.app/Contents/MacOS/soffice';
  execFileSync(so, ['--headless', '--convert-to', 'pdf', '--outdir', tmp, tp], { stdio: 'ignore', timeout: 600000 });
}
if (!fs.existsSync(pdf)) { console.error('render failed: no PDF from ' + renderer); process.exit(1); }
// 2. PDF -> PNG
if (!which('pdftoppm')) { console.error('pdftoppm (poppler) is required: brew install poppler'); process.exit(1); }
execFileSync('pdftoppm', ['-r', '110', '-png', pdf, path.join(qa, 'p')]);
fs.rmSync(tp, { force: true }); fs.rmSync(pdf, { force: true });
const pages = fs.readdirSync(qa).filter(f => /^p-\d+\.png$/.test(f)).sort((x, y) => parseInt(x.slice(2)) - parseInt(y.slice(2)));
if (pages.length !== manifest.slides.length) console.log(`WARN rendered ${pages.length} pages, expected ${manifest.slides.length}`);

// 3. compare in a browser canvas (no native image deps)
const b64 = f => 'data:image/png;base64,' + fs.readFileSync(f).toString('base64');
const browser = await (async () => { for (const c of a.browser ? [a.browser] : ['chromium', 'msedge', 'chrome']) { try { return await chromium.launch(c === 'chromium' ? {} : { channel: c }); } catch (e) { if (a.browser) throw e; } } throw new Error('no browser'); })();
const page = await browser.newPage();
const rows = [];
for (let i = 0; i < pages.length && i < manifest.slides.length; i++) {
  const s = manifest.slides[i];
  const ref = path.join(work, 'ref', s.id.slice(1).padStart(2, '0') + '.png');
  if (!fs.existsSync(ref)) continue;
  const score = await page.evaluate(async ([h, p]) => {
    const load = src => new Promise(ok => { const im = new Image(); im.onload = () => ok(im); im.src = src; });
    const [A, B] = await Promise.all([load(h), load(p)]);
    const W = 320, H = Math.round(320 * A.height / A.width);
    const px = im => { const c = document.createElement('canvas'); c.width = W; c.height = H; const x = c.getContext('2d'); x.drawImage(im, 0, 0, W, H); return x.getImageData(0, 0, W, H).data; };
    const da = px(A), db = px(B); let sum = 0, bad = 0;
    for (let k = 0; k < da.length; k += 4) { const d = (Math.abs(da[k] - db[k]) + Math.abs(da[k + 1] - db[k + 1]) + Math.abs(da[k + 2] - db[k + 2])) / 3; sum += d; if (d > 40) bad++; }
    return { mean: +(sum / (W * H)).toFixed(2), badPct: +(100 * bad / (W * H)).toFixed(2) };
  }, [b64(ref), b64(path.join(qa, pages[i]))]);
  rows.push({ n: i + 1, id: s.id, title: s.title, ref, png: path.join(qa, pages[i]), ...score });
}

// 4. side-by-side sheets
const per = +(a['per-sheet'] || 4), Wc = +(a.width || 560);
const sheets = [];
for (let i = 0; i < rows.length; i += per) {
  const chunk = rows.slice(i, i + per);
  await page.setViewportSize({ width: Wc * 2 + 36, height: 200 });
  await page.setContent(`<body style="margin:0;padding:8px;background:#fff;font:12px system-ui">${chunk.map(r => `
    <div style="display:flex;gap:12px;margin-bottom:8px;position:relative">
      <img src="${b64(r.ref)}" style="width:${Wc}px;border:1px solid #ccc"><img src="${b64(r.png)}" style="width:${Wc}px;border:1px solid #ccc">
      <div style="position:absolute;left:4px;top:2px;color:#d00;font-weight:700;background:#fff8">${r.n} HTML</div>
      <div style="position:absolute;left:${Wc + 16}px;top:2px;color:#d00;font-weight:700;background:#fff8">${r.n} PPTX · diff ${r.badPct}%</div>
    </div>`).join('')}</body>`);
  const f = path.join(qa, `sheet-${String(i / per + 1).padStart(2, '0')}.png`);
  await page.screenshot({ path: f, fullPage: true });
  sheets.push(f);
}
await browser.close();
fs.writeFileSync(path.join(qa, 'report.json'), JSON.stringify(rows.map(({ ref, png, ...r }) => r), null, 1));
const ranked = [...rows].sort((x, y) => y.badPct - x.badPct);
console.log(`renderer: ${renderer} · ${rows.length} slides compared · sheets: ${sheets.length} in ${qa}`);
console.log('most different slides (badPct = % of pixels differing noticeably at 320px):');
ranked.slice(0, 10).forEach(r => console.log(`  ${String(r.n).padStart(2)}  ${String(r.badPct).padStart(6)}%  mean ${String(r.mean).padStart(5)}  ${r.title.slice(0, 70)}`));

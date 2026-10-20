#!/usr/bin/env node
// html2pptx: convert an HTML slide deck into a native, editable PowerPoint file.
// Usage: node html2pptx.mjs <deck.html | http(s)://url> -o out.pptx [options]   (see --help)
import fs from 'node:fs';
import path from 'node:path';
import { parseArgs } from 'node:util';
import { chromium } from 'playwright';
import { serve } from './lib/server.mjs';
import { extractDeck } from './lib/extract.mjs';
import { prepareVideos } from './lib/video.mjs';
import { buildPptx } from './lib/build.mjs';
import { postProcess } from './lib/post.mjs';

const HELP = `html2pptx <deck.html|url> -o out.pptx [options]
  --selector CSS          slide elements (default: auto-detect section.slide, .slide, reveal.js, ...)
  --size WxH              design size in CSS px (default: first slide's layout size)
  --slides 1,3,5-8        only convert these slides (1-based)
  --hide CSS              extra deck chrome to hide (buttons, counters)
  --player-selector CSS   wrapper element of custom video players
  --no-video              replace videos with their poster frame (small file)
  --burn-captions         burn <track>/data-cues captions into embedded videos (ffmpeg)
  --video-speed N         re-time embedded videos (e.g. 1.25)
  --video-crf N           x264 quality when re-encoding (default 28)
  --font-fallback NAME    font for generic families (default "Segoe UI")
  --font-map A=B,C=D      map web fonts to installed fonts (e.g. Inter=Aptos)
  --keep-fonts            keep web/system font names (default: first Office-safe font in each CSS stack)
  --no-builds             keep fragments/build steps in their initial (hidden) state
  --settle MS             wait after navigation (default 350)
  --browser NAME          chromium | msedge | chrome (default: first that launches)
  --work DIR              working dir (default: <out>.work) — keep it for qa.mjs
  --title/--author/--company/--subject TEXT   document properties`;

const { values: a, positionals } = parseArgs({
  allowPositionals: true,
  options: {
    out: { type: 'string', short: 'o' }, selector: { type: 'string' }, size: { type: 'string' }, slides: { type: 'string' },
    hide: { type: 'string' }, 'player-selector': { type: 'string' }, 'no-video': { type: 'boolean' }, 'burn-captions': { type: 'boolean' },
    'video-speed': { type: 'string' }, 'video-crf': { type: 'string' }, 'font-fallback': { type: 'string' }, 'font-map': { type: 'string' },
    'no-builds': { type: 'boolean' }, 'keep-fonts': { type: 'boolean' }, settle: { type: 'string' }, browser: { type: 'string' }, work: { type: 'string' },
    title: { type: 'string' }, author: { type: 'string' }, company: { type: 'string' }, subject: { type: 'string' }, help: { type: 'boolean', short: 'h' },
  },
});
if (a.help || !positionals[0]) { console.log(HELP); process.exit(a.help ? 0 : 2); }

const input = positionals[0];
const isUrl = /^https?:\/\//i.test(input);
if (!isUrl && !fs.existsSync(input)) { console.error('input not found: ' + input); process.exit(2); }
const out = path.resolve(a.out || (isUrl ? 'deck.pptx' : input.replace(/\.html?$/i, '') + '.pptx'));
const work = path.resolve(a.work || out.replace(/\.pptx$/i, '') + '.work');
fs.rmSync(path.join(work, 'assets'), { recursive: true, force: true });
fs.rmSync(path.join(work, 'ref'), { recursive: true, force: true });
fs.mkdirSync(work, { recursive: true });
const log = m => console.log(m);
const parseSlides = s => s ? s.split(',').flatMap(p => { const [x, y] = p.split('-').map(Number); return y ? Array.from({ length: y - x + 1 }, (_, i) => x + i) : [x]; }) : null;
const [sw, sh] = a.size ? a.size.split('x').map(Number) : [0, 0];
const fontMap = {};
(a['font-map'] || '').split(',').filter(Boolean).forEach(p => { const [k, v] = p.split('='); fontMap[k.trim().toLowerCase()] = v.trim(); });

async function launch() {
  const order = a.browser ? [a.browser] : ['chromium', 'msedge', 'chrome'];
  for (const b of order) {
    try { return await chromium.launch(b === 'chromium' ? {} : { channel: b }); } catch (e) { if (a.browser) throw e; }
  }
  throw new Error('No Chromium-based browser could be launched. Run: npx playwright install chromium');
}

let server = null, browser = null;
try {
  let url = input;
  if (!isUrl) {
    const abs = path.resolve(input);
    server = await serve(path.dirname(abs));
    url = `http://127.0.0.1:${server.port}/${encodeURIComponent(path.basename(abs))}`;
  }
  browser = await launch();
  log(`browser: ${browser.version()}  input: ${isUrl ? url : path.resolve(input)}`);
  const ctx = await browser.newContext({ viewport: { width: sw || 1600, height: sh || 900 }, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  page.on('pageerror', e => log('  page error: ' + String(e.message || e).slice(0, 160)));
  const deck = await extractDeck(page, {
    url, work, selector: a.selector, width: sw, height: sh, slides: parseSlides(a.slides), hide: a.hide, playerSelector: a['player-selector'],
    settle: +(a.settle || 350), builds: !a['no-builds'], fontMap, keepFonts: !!a['keep-fonts'], fontFallback: a['font-fallback'] || 'Segoe UI', log,
  });
  fs.writeFileSync(path.join(work, 'plan.json'), JSON.stringify(deck));
  if (!a['no-video']) await prepareVideos(deck, { work, server, browser, speed: +(a['video-speed'] || 1), burn: !!a['burn-captions'], crf: +(a['video-crf'] || 28), log });
  const { buf, grad, failures, size } = await buildPptx(deck, { work, noVideo: !!a['no-video'], title: a.title || deck.slides[0]?.title, author: a.author, company: a.company, subject: a.subject });
  const { out: final, nS, nT, deduped } = await postProcess(buf, grad);
  fs.writeFileSync(out, final);
  fs.writeFileSync(path.join(work, 'manifest.json'), JSON.stringify({ input: isUrl ? url : path.resolve(input), out, W: deck.W, H: deck.H, slides: deck.slides.map(s => ({ id: s.id, title: s.title, mode: s.mode })) }, null, 1));
  const items = deck.slides.reduce((n, s) => n + s.items.length, 0), rasters = deck.slides.reduce((n, s) => n + s.rasters.length, 0);
  const forced = deck.slides.filter(s => s.mode.startsWith('forced')).map(s => s.id + ':' + s.mode);
  const empty = deck.slides.filter(s => !s.textCount).map(s => s.id);
  const navs = [...new Set(deck.slides.map(s => s.mode.split('(')[0]))].join('/');
  log(`\n${deck.slides.length} slides, ${items} items (${rasters} rasters), ${nS} gradient shapes, ${nT} gradient texts, ${deduped} duplicate media removed`);
  log(`slide size ${size.SW}x${size.SH} in · ${(final.length / 1e6).toFixed(1)} MB -> ${out}`);
  const fonts = {}; deck.slides.forEach(s => Object.assign(fonts, s.fonts || {}));
  log(`navigation: ${navs} · fonts: ${Object.entries(fonts).map(([k, v]) => k === v ? k : `${k}→${v}`).join(', ')}`);
  if (forced.length) log(`WARN isolated via CSS because deck navigation did not show them — check these in QA: ${forced.join(' ')}`);
  if (empty.length) log(`WARN slides with no extracted text (empty or all-image?): ${empty.join(' ')}`);
  if (failures.length) { log(`WARN ${failures.length} items failed:`); failures.slice(0, 20).forEach(f => log('  ' + f)); }
  log(`work dir (for qa.mjs): ${work}`);
} catch (e) {
  console.error('FAILED: ' + (e.stack || e));
  process.exitCode = 1;
} finally {
  if (browser) await browser.close().catch(() => {});
  if (server) server.close();
}

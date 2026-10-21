// Video handling: resolve <video> sources to local files, optionally burn captions / change speed / recompress (ffmpeg).
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

const has = bin => { try { execFileSync(bin, ['-version'], { stdio: 'ignore' }); return true; } catch { return false; } };
const probe = f => {
  const j = JSON.parse(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'stream=codec_type,width,height:format=duration', '-of', 'json', f]).toString());
  const v = j.streams.find(s => s.codec_type === 'video') || {};
  return { w: v.width, h: v.height, dur: +j.format.duration, audio: j.streams.some(s => s.codec_type === 'audio') };
};

function parseVtt(txt) {
  const t = s => { const p = s.trim().split(':').map(parseFloat); return p.length === 3 ? p[0] * 3600 + p[1] * 60 + p[2] : p[0] * 60 + p[1]; };
  const out = [];
  for (const block of txt.replace(/\r/g, '').split(/\n\n+/)) {
    const lines = block.split('\n'); const i = lines.findIndex(l => l.includes('-->'));
    if (i < 0) continue;
    const [a, b] = lines[i].split('-->'); const text = lines.slice(i + 1).join(' ').replace(/<[^>]+>/g, '').trim();
    if (text) out.push([t(a), t(b.trim().split(/\s+/)[0]), text]);
  }
  return out;
}

async function localFile(src, server, work) {
  if (!src) return null;
  if (src.startsWith('data:')) { const m = /^data:([^;]+);base64,(.*)$/.exec(src); if (!m) return null; const f = path.join(work, 'media', 'inline-' + Date.now() + '.mp4'); fs.writeFileSync(f, Buffer.from(m[2], 'base64')); return f; }
  const u = new URL(src);
  if (server && u.host === `127.0.0.1:${server.port}`) return path.join(server.root, decodeURIComponent(u.pathname));
  if (u.protocol === 'file:') return decodeURIComponent(u.pathname);
  const r = await fetch(src); if (!r.ok) return null;
  const f = path.join(work, 'media', path.basename(u.pathname) || 'video.mp4'); fs.writeFileSync(f, Buffer.from(await r.arrayBuffer())); return f;
}

async function textOf(url, server) {
  const u = new URL(url);
  if (server && u.host === `127.0.0.1:${server.port}`) return fs.readFileSync(path.join(server.root, decodeURIComponent(u.pathname)), 'utf8');
  const r = await fetch(url); return r.ok ? r.text() : '';
}

async function renderBand(page, text, W, Hb, fpx, file, font) {
  await page.setViewportSize({ width: W, height: Hb });
  await page.setContent(`<html><body style="margin:0;width:${W}px;height:${Hb}px;background:#151A2E;display:flex;align-items:center;justify-content:center;overflow:hidden">
    <div style="color:#F3F5FF;font:${fpx}px/1.3 ${font};text-align:center;max-width:92%">${text.replace(/&/g, '&amp;').replace(/</g, '&lt;')}</div></body></html>`);
  await page.screenshot({ path: file, clip: { x: 0, y: 0, width: W, height: Hb } });
}

export async function prepareVideos(deck, { work, server, browser, speed = 1, burn = false, crf = 28, maxWidth = 1280, font = "'Segoe UI', Arial, sans-serif", log = () => {} }) {
  const vids = deck.slides.flatMap(s => s.items.filter(i => i.t === 'video'));
  if (!vids.length) return;
  fs.mkdirSync(path.join(work, 'media'), { recursive: true });
  const ff = has('ffmpeg') && has('ffprobe');
  const done = new Map();
  for (const it of vids) {
    const src = await localFile(it.src, server, work).catch(() => null);
    if (!src || !fs.existsSync(src)) { log(`  video not found: ${it.src} (cover image only)`); continue; }
    let cues = it.cues || null;
    if (!cues && it.track) cues = parseVtt(await textOf(it.track, server).catch(() => ''));
    const key = src + '|' + JSON.stringify(cues || []);
    if (done.has(key)) { Object.assign(it, done.get(key)); continue; }
    if (!ff) { if (/\.mp4$|\.m4v$|\.mov$/i.test(src)) { it.file = src; } else log(`  ffmpeg missing: cannot convert ${path.basename(src)}`); done.set(key, { file: it.file }); continue; }
    const info = probe(src);
    const wantBurn = burn && cues && cues.length;
    const big = fs.statSync(src).size > 15e6;
    if (!wantBurn && speed === 1 && !big && /\.mp4$/i.test(src)) { it.file = src; it.ar = info.w / info.h; done.set(key, { file: src, ar: it.ar }); continue; }
    const W = Math.min(maxWidth, info.w) - (Math.min(maxWidth, info.w) % 2);
    const out = path.join(work, 'media', `${path.basename(src).replace(/\.[^.]+$/, '')}-${done.size}.mp4`);
    const vf = [], args = ['-v', 'error', '-y', '-i', src];
    let filter;
    if (wantBurn) {
      let bandH = Math.round(W * 0.072); bandH += bandH % 2; const fpx = Math.round(bandH * 0.34);
      const d = path.join(work, 'media', 'band-' + done.size); fs.mkdirSync(d, { recursive: true });
      const page = await browser.newPage();
      const blank = path.join(d, 'blank.png'); await renderBand(page, '', W, bandH, fpx, blank, font);
      const segs = []; let t = 0;
      for (let i = 0; i < cues.length; i++) {
        const [a, b, txt] = cues[i];
        if (a > t + 0.01) segs.push([blank, a - t]);
        const p = path.join(d, `c${String(i).padStart(4, '0')}.png`); await renderBand(page, String(txt), W, bandH, fpx, p, font);
        segs.push([p, Math.max(0.04, b - Math.max(a, t))]); t = Math.max(t, b);
      }
      await page.close();
      if (info.dur > t) segs.push([blank, info.dur - t]);
      const lst = path.join(d, 'list.txt');
      fs.writeFileSync(lst, segs.map(([p, du]) => `file '${p}'\nduration ${du.toFixed(3)}\n`).join('') + `file '${segs[segs.length - 1][0]}'\n`);
      args.push('-f', 'concat', '-safe', '0', '-i', lst);
      filter = `[1:v]fps=30,scale=${W}:${bandH},format=yuv420p,setsar=1[b];[0:v]scale=${W}:-2,setsar=1[m];[m][b]vstack=inputs=2`;
    } else filter = `[0:v]scale=${W}:-2,setsar=1`;
    filter += speed !== 1 ? `,setpts=PTS/${speed},fps=30[v]` : ',fps=30[v]';
    if (info.audio) filter += speed !== 1 ? `;[0:a]atempo=${speed}[a]` : ';[0:a]anull[a]';
    args.push('-filter_complex', filter, '-map', '[v]');
    if (info.audio) args.push('-map', '[a]', '-c:a', 'aac', '-b:a', '64k', '-ac', '1');
    args.push('-t', String(info.dur / speed), '-c:v', 'libx264', '-preset', 'slow', '-crf', String(crf), '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out);
    execFileSync('ffmpeg', args, { stdio: ['ignore', 'ignore', 'inherit'] });
    const pi = probe(out);
    Object.assign(it, { file: out, ar: pi.w / pi.h, burned: !!wantBurn });
    done.set(key, { file: out, ar: it.ar, burned: it.burned });
    log(`  video ${path.basename(src)} -> ${path.basename(out)} ${(fs.statSync(out).size / 1e6).toFixed(1)} MB${wantBurn ? ', captions burned' : ''}${speed !== 1 ? `, ${speed}x` : ''}`);
  }
}

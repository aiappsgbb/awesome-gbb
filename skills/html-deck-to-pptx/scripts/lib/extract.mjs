// Browser-side extraction: walks each slide's DOM and produces a build plan of native items
// (shapes, text runs, tables, videos) plus rasters for things PowerPoint cannot express natively.
import fs from 'node:fs';
import path from 'node:path';
import { PNG } from 'pngjs';

const BASE_CSS = `
  html.__h2p *, html.__h2p *::before, html.__h2p *::after{transition-duration:0s!important;transition-delay:0s!important;caret-color:transparent!important}
  html.__h2p [data-h2p-chrome]{visibility:hidden!important}
  html.__h2p_builds .fragment, html.__h2p_builds .step, html.__h2p_builds [data-fragment-index], html.__h2p_builds [data-step]{opacity:1!important;visibility:visible!important;transform:none!important}
  html.__h2p_force [data-h2p-slide]:not([data-h2p-cur]){display:none!important}
  html.__h2p_force [data-h2p-cur]{visibility:visible!important;opacity:1!important;transform:none!important;position:fixed!important;left:0!important;top:0!important;margin:0!important;z-index:2147483000!important}
  html.__iso *, html.__iso *::before, html.__iso *::after{visibility:hidden!important;animation:none!important}
  html.__iso [data-rxon], html.__iso [data-rxon]::before, html.__iso [data-rxon]::after{visibility:visible!important}
  html.__iso [data-rxshell]{color:transparent!important;-webkit-text-fill-color:transparent!important;text-shadow:none!important;text-decoration-color:transparent!important}
  html.__iso [data-rxdeep] *, html.__iso [data-rxdeep] *::before, html.__iso [data-rxdeep] *::after{visibility:visible!important}
  html.__iso marker, html.__iso marker *, html.__iso defs, html.__iso defs *, html.__iso symbol, html.__iso symbol *, html.__iso linearGradient, html.__iso radialGradient, html.__iso stop, html.__iso clipPath, html.__iso clipPath *, html.__iso mask, html.__iso mask *, html.__iso pattern, html.__iso pattern *{visibility:visible!important}
  html.__iso, html.__iso body{background:transparent!important}
  html.__bg [data-h2p-cur] *, html.__bg [data-h2p-cur] *::before, html.__bg [data-h2p-cur] *::after{visibility:hidden!important}
  html.__bg [data-h2p-cur] [data-bake], html.__bg [data-h2p-cur] [data-bake] *{visibility:visible!important}
`;

const AUTO_SELECTORS = ['.reveal .slides section', '.remark-slide-container', 'section.slide', '.slide', '[data-slide]', '.step.slide', 'main > section', 'body > section'];

// ---------- page-side helpers (serialized into the page) ----------
function pageDetect({ selector, auto }) {
  const pick = sel => [...document.querySelectorAll(sel)].filter((e, _, all) => !all.some(o => o !== e && e.contains(o)));
  let sel = selector, list = selector ? pick(selector) : [];
  if (!selector) for (const min of [2, 1]) { for (const s of auto) { const l = pick(s); if (l.length >= min) { sel = s; list = l; break; } } if (list.length) break; }
  list.forEach((e, i) => e.setAttribute('data-h2p-slide', String(i)));
  // frameworks that scale a fixed-size stage and position slides inside it: measure the stage
  const stage = list[0] && list[0].closest('.reveal .slides');
  if (stage) stage.setAttribute('data-h2p-frame', '1');
  const f = list[0] ? (list[0].closest('[data-h2p-frame]') || list[0]) : null;
  return { selector: sel, count: list.length, w: f ? f.offsetWidth : 0, h: f ? f.offsetHeight : 0, ids: list.map(e => e.id || '') };
}

function pageShow(k) {
  const S = document.querySelector(`[data-h2p-slide="${k}"]`);
  document.documentElement.classList.remove('__h2p_force');
  document.querySelectorAll('[data-h2p-cur]').forEach(e => { e.removeAttribute('data-h2p-cur'); if (e.__h2pStyle !== undefined) { e.setAttribute('style', e.__h2pStyle); delete e.__h2pStyle; } });
  S.setAttribute('data-h2p-cur', '1');
  if (window.Reveal && typeof window.Reveal.getIndices === 'function') { const i = window.Reveal.getIndices(S); window.Reveal.slide(i.h, i.v || 0, 0); }
  else if (S.id && location.hash !== '#' + S.id) location.hash = '#' + S.id;
}

function pageChrome({ k, hide }) {
  const S = document.querySelector(`[data-h2p-slide="${k}"]`);
  document.getAnimations().forEach(a => { try { a.finish(); } catch (e) { try { a.pause(); a.currentTime = 0; } catch (e2) { /* ignore */ } } });
  // hide deck chrome (nav buttons, progress bars, slide counters) that sits outside the slide
  document.querySelectorAll('[data-h2p-chrome]').forEach(e => e.removeAttribute('data-h2p-chrome'));
  const vpA = innerWidth * innerHeight;
  for (const e of document.body.querySelectorAll('*')) {
    if (e.contains(S) || S.contains(e) || e.closest('[data-h2p-slide]')) continue;
    const cs = getComputedStyle(e); const r = e.getBoundingClientRect();
    const fixed = cs.position === 'fixed' || cs.position === 'sticky';
    const cls = typeof e.className === 'string' ? e.className : '';
    const chromeLike = /^(BUTTON|NAV)$/.test(e.tagName) || /control|progress|nav|counter|pager|toolbar|slide-number|hint/i.test(cls);
    if ((fixed || chromeLike) && r.width * r.height < 0.3 * vpA) e.setAttribute('data-h2p-chrome', '1');
  }
  if (hide) document.querySelectorAll(hide).forEach(e => { if (e !== S && !e.contains(S)) e.setAttribute('data-h2p-chrome', '1'); });
}

function pageVisible(k) {
  const S = document.querySelector(`[data-h2p-slide="${k}"]`);
  document.getAnimations().forEach(a => { try { a.finish(); } catch (e) { /* ignore */ } });
  const r = S.getBoundingClientRect();
  const inView = r.width > 10 && r.left > -2 && r.top > -2 && r.right < innerWidth + 2 && r.bottom < innerHeight + 2;
  let op = 1; for (let e = S; e && e.nodeType === 1; e = e.parentElement) { const c = getComputedStyle(e); op *= +c.opacity; if (c.visibility === 'hidden' || c.display === 'none') op = 0; }
  const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
  return inView && op > 0.95 && !!hit && (S.contains(hit) || hit.contains(S));
}

function pageForce({ k, W, H }) {
  const S = document.querySelector(`[data-h2p-slide="${k}"]`);
  document.documentElement.classList.add('__h2p_force');
  S.__h2pStyle = S.getAttribute('style') || '';
  S.style.setProperty('width', W + 'px', 'important'); S.style.setProperty('height', H + 'px', 'important');
  if (getComputedStyle(S).display === 'none') S.style.setProperty('display', 'block', 'important');
  ['active', 'present', 'current', 'is-active', 'visible'].forEach(c => S.classList.add(c));
  document.getAnimations().forEach(a => { try { a.finish(); } catch (e) { /* ignore */ } });
  // build steps hidden by the deck's own script: show everything that is merely transparent
  let n = 0;
  for (const e of S.querySelectorAll('*')) { const c = getComputedStyle(e); if (c.display !== 'none' && +c.opacity === 0) { e.style.setProperty('opacity', '1', 'important'); e.style.setProperty('transform', 'none', 'important'); n++; } }
  return n;
}

function pageExtract({ k, fontMap, fontFallback, playerSel, keepFonts }) {
  const S = document.querySelector(`[data-h2p-slide="${k}"]`);
  const sid = 's' + String(k + 1).padStart(2, '0');
  const FR = S.closest('[data-h2p-frame]') || S;
  const R = FR.getBoundingClientRect();
  const sc = R.width / FR.offsetWidth;
  const box = r => ({ x: (r.left - R.left) / sc, y: (r.top - R.top) / sc, w: r.width / sc, h: r.height / sc });
  const items = [];
  const rasters = [];
  let rx = 0;
  const pc = s => parseFloat(s) || 0;
  document.querySelectorAll('[data-rxid],[data-bake],[data-h2p-player]').forEach(e => { e.removeAttribute('data-rxid'); e.removeAttribute('data-bake'); e.removeAttribute('data-h2p-player'); });

  const rgba = s => {
    if (!s) return null;
    const m = s.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(/[\s,/]+/).filter(Boolean).map(Number);
    const a = p.length > 3 ? p[3] : 1;
    if (a === 0) return null;
    const hex = p.slice(0, 3).map(v => Math.round(v).toString(16).padStart(2, '0')).join('').toUpperCase();
    return { hex, a };
  };
  const splitTop = s => { const out = []; let d = 0, cur = ''; for (const ch of s) { if (ch === '(') d++; if (ch === ')') d--; if (ch === ',' && d === 0) { out.push(cur.trim()); cur = ''; } else cur += ch; } if (cur.trim()) out.push(cur.trim()); return out; };
  const parseLinear = bi => {
    if (!bi || bi === 'none') return null;
    const layers = splitTop(bi);
    if (layers.length !== 1) return null;
    const m = layers[0].match(/^linear-gradient\((.*)\)$/);
    if (!m) return null;
    const parts = splitTop(m[1]);
    let ang = 180;
    if (/deg$/.test(parts[0])) ang = parseFloat(parts.shift());
    else if (/^to /.test(parts[0])) { const t = parts.shift(); ang = { 'to top': 0, 'to right': 90, 'to bottom': 180, 'to left': 270, 'to top right': 45, 'to bottom right': 135, 'to bottom left': 225, 'to top left': 315 }[t] ?? 180; }
    const stops = parts.map(p => { const c = rgba(p.match(/rgba?\([^)]+\)/)?.[0] || ''); const pm = p.match(/\)\s*([\d.]+)%/); return c ? { c: c.hex, a: c.a, p: pm ? parseFloat(pm[1]) : null } : null; }).filter(Boolean);
    if (stops.length < 2) return null;
    stops.forEach((s, i) => { if (s.p === null) s.p = i === 0 ? 0 : i === stops.length - 1 ? 100 : null; });
    for (let i = 1; i < stops.length - 1; i++) if (stops[i].p === null) { let j = i; while (stops[j].p === null) j++; const a = stops[i - 1].p, b = stops[j].p; for (let t = i; t < j; t++) stops[t].p = a + (b - a) * (t - i + 1) / (j - i + 1); }
    return { ang, stops };
  };
  const shadowOf = cs => {
    const s = cs.boxShadow; if (!s || s === 'none') return null;
    const first = splitTop(s).find(x => !/inset/.test(x)); if (!first) return null;
    const col = rgba(first.match(/rgba?\([^)]+\)/)?.[0] || ''); if (!col) return null;
    const nums = first.replace(/rgba?\([^)]+\)/, '').trim().split(/\s+/).map(pc);
    const [ox, oy, blur, spread] = [nums[0] || 0, nums[1] || 0, nums[2] || 0, nums[3] || 0];
    let op = col.a; if (spread < 0) op *= 0.45;
    if (op < 0.04) return null;
    return { ox, oy, blur, op, c: col.hex };
  };
  const visiblePseudo = (el, which) => {
    const p = getComputedStyle(el, which);
    if (!p || p.content === 'none' || p.content === 'normal' || p.display === 'none' || p.visibility === 'hidden') return null;
    const bg = rgba(p.backgroundColor), bi = p.backgroundImage !== 'none';
    const bw = ['Top', 'Right', 'Bottom', 'Left'].map(sd => pc(p['border' + sd + 'Width']));
    const txt = p.content.replace(/^["']|["']$/g, '');
    if (!bg && !bi && !bw.some(Boolean) && !txt) return null;
    const inset = p.position === 'absolute' && pc(p.top) === 0 && pc(p.left) === 0 && p.right === '0px' && p.bottom === '0px';
    if (inset && !bg && !txt) {
      if (!bi && bw.every(w => w === bw[0])) return { kind: 'border', w: bw[0], c: rgba(p.borderTopColor) };
      if (bi && p.webkitMaskImage && p.webkitMaskImage !== 'none') { const g = parseLinear(p.backgroundImage); if (g) return { kind: 'border', w: pc(p.paddingTop) || 1.5, c: { hex: g.stops[0].c, a: 1 }, grad: g }; }
    }
    return { kind: 'raster' };
  };
  const GENERIC = new Set(['system-ui', '-apple-system', 'blinkmacsystemfont', 'ui-sans-serif', 'ui-serif', 'ui-monospace', 'ui-rounded', 'sans-serif', 'serif', 'monospace', 'cursive', 'fantasy', 'emoji', 'math']);
  // fonts that ship with Microsoft Office / Windows + macOS Office installs: safe to reference in a PPTX
  const OFFICE = new Set(['segoe ui', 'segoe ui light', 'segoe ui semilight', 'segoe ui semibold', 'segoe ui black', 'segoe ui variable', 'aptos', 'aptos display', 'aptos narrow', 'aptos mono', 'calibri', 'calibri light', 'cambria', 'candara', 'consolas', 'constantia', 'corbel', 'arial', 'arial black', 'arial narrow', 'georgia', 'times new roman', 'verdana', 'tahoma', 'trebuchet ms', 'courier new', 'garamond', 'century gothic', 'gill sans mt', 'franklin gothic medium', 'franklin gothic book', 'bahnschrift', 'palatino linotype', 'book antiqua', 'lucida console', 'lucida sans unicode', 'impact', 'comic sans ms', 'grandview', 'seaford', 'tenorite', 'bierstadt', 'skeena', 'sitka text', 'rockwell', 'cascadia code', 'cascadia mono']);
  const fontLog = {};
  const fontOf = cs => {
    const fams = cs.fontFamily.split(',').map(f => f.trim().replace(/^["']|["']$/g, ''));
    const w = +cs.fontWeight;
    const lc = fams.map(f => f.toLowerCase());
    let fam = null;
    if (keepFonts) fam = fams.find((f, i) => !GENERIC.has(lc[i]));
    else for (let i = 0; i < fams.length && !fam; i++) { if (fontMap[lc[i]]) fam = fontMap[lc[i]]; else if (OFFICE.has(lc[i])) fam = fams[i]; }
    if (!fam) {
      const mono = lc.some(f => f === 'monospace' || f === 'ui-monospace' || /mono|code|courier|menlo|consol/.test(f));
      const serif = !mono && lc.some(f => f === 'serif' || f === 'ui-serif');
      fam = mono ? (fontMap.__mono || 'Consolas') : serif ? (fontMap.__serif || 'Georgia') : fontFallback;
    }
    if (/^cascadia/i.test(fam) && !keepFonts) fam = 'Consolas';
    fontLog[fams[0]] = fam;
    if (/^segoe ui$/i.test(fam)) {
      if (w <= 300) return { face: 'Segoe UI Light', bold: false };
      if (w < 400) return { face: 'Segoe UI Semilight', bold: false };
      if (w < 600) return { face: 'Segoe UI', bold: false };
      if (w < 700) return { face: 'Segoe UI Semibold', bold: false };
      return { face: 'Segoe UI', bold: true };
    }
    return { face: fam, bold: w >= 600 };
  };
  const hidden = (el, cs) => cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity === 0;
  const SKIPTAG = new Set(['SCRIPT', 'STYLE', 'TEMPLATE', 'NOSCRIPT', 'LINK', 'META']);
  const isNotes = el => el.matches('aside.notes, .notes, .speaker-notes, [data-notes-body]');
  const hasText = e => /\S/.test(e.textContent || '');
  const isInline = e => {
    if (e.nodeType === 3) return true;
    if (e.nodeType !== 1) return true;
    if (e.tagName === 'BR') return true;
    if (/^(SVG|IMG|VIDEO|TABLE|CANVAS|IFRAME|svg)$/.test(e.tagName) || e.hasAttribute('data-h2p-player')) return false;
    const cs = getComputedStyle(e);
    if (hidden(e, cs)) return true;
    if (cs.display === 'inline') return [...e.childNodes].every(isInline);
    if (/^inline-(flex|block)$/.test(cs.display) && hasText(e) && e.parentElement && pc(cs.fontSize) >= 0.6 * pc(getComputedStyle(e.parentElement).fontSize) && [...e.parentElement.childNodes].some(n => n !== e && n.nodeType === 3 && /\S/.test(n.textContent)) && [...e.childNodes].every(n => n.nodeType === 3 || (n.nodeType === 1 && getComputedStyle(n).display === 'inline' && !n.querySelector('svg')))) return true;
    return false;
  };
  const gradTextOf = el => {
    let x = el;
    while (x && x !== S.parentElement) {
      const c = getComputedStyle(x);
      if (c.webkitBackgroundClip === 'text' || c.backgroundClip === 'text') { const g = parseLinear(c.backgroundImage); if (g) g.el = x; return g; }
      x = x.parentElement;
    }
    return null;
  };
  const runsOf = (nodes, root) => {
    const runs = [];
    const push = (txt, el) => {
      const cs = getComputedStyle(el);
      const col = rgba(cs.webkitTextFillColor && cs.webkitTextFillColor !== cs.color ? cs.webkitTextFillColor : cs.color) || rgba(cs.color);
      const f = fontOf(cs);
      let a = el.closest('a[href]'); if (a && getComputedStyle(a).display !== 'inline') a = null;
      let bgEl = el, hl = null;
      while (bgEl && bgEl !== root && /^inline/.test(getComputedStyle(bgEl).display)) { const b = rgba(getComputedStyle(bgEl).backgroundColor); if (b) { hl = b.hex; break; } bgEl = bgEl.parentElement; }
      let t = txt;
      if (cs.textTransform === 'uppercase') t = t.toUpperCase();
      else if (cs.textTransform === 'lowercase') t = t.toLowerCase();
      let grad = gradTextOf(el);
      if (grad && grad.el) {
        const er = grad.el.getBoundingClientRect(); const rg = document.createRange(); rg.selectNodeContents(grad.el); const tr = rg.getBoundingClientRect();
        const f0 = Math.max(0, (tr.left - er.left) / er.width), f1 = Math.min(1, (tr.right - er.left) / er.width);
        const at = q => { const st = grad.stops; const P = q * 100; let i = 0; while (i < st.length - 2 && st[i + 1].p < P) i++; const A = st[i], B = st[i + 1]; const kk = B.p === A.p ? 0 : Math.max(0, Math.min(1, (P - A.p) / (B.p - A.p))); const h = (s, j) => parseInt(s.slice(j, j + 2), 16); return [0, 2, 4].map(j => Math.round(h(A.c, j) + (h(B.c, j) - h(A.c, j)) * kk).toString(16).padStart(2, '0')).join('').toUpperCase(); };
        grad = { ang: grad.ang, stops: [0, 0.25, 0.5, 0.75, 1].map(q => ({ c: at(f0 + (f1 - f0) * q), a: 1, p: q * 100 })) };
      }
      runs.push({ t, size: pc(cs.fontSize), face: f.face, bold: f.bold, italic: cs.fontStyle === 'italic', u: /underline/.test(cs.textDecorationLine), strike: /line-through/.test(cs.textDecorationLine), sup: cs.verticalAlign === 'super', sub: cs.verticalAlign === 'sub', color: col ? col.hex : '000000', alpha: col ? col.a : 1, ls: cs.letterSpacing === 'normal' ? 0 : pc(cs.letterSpacing), href: a ? a.getAttribute('href') : null, hl, grad });
    };
    const walk = n => {
      if (n.nodeType === 3) {
        const pe = n.parentElement; const cs = getComputedStyle(pe);
        let t = n.textContent;
        if (!/pre/.test(cs.whiteSpace)) t = t.replace(/\s+/g, ' ');
        if (t) {
          if (/pre/.test(cs.whiteSpace) && t.includes('\n')) t.split('\n').forEach((ln, i) => { if (i) runs.push({ br: true }); if (ln) push(ln, pe); });
          else push(t, pe);
        }
      } else if (n.nodeType === 1) {
        if (n.tagName === 'BR') { runs.push({ br: true }); return; }
        const cs = getComputedStyle(n); if (hidden(n, cs)) return;
        const last = runs.filter(r => !r.br).slice(-1)[0];
        if (pc(cs.marginLeft) + pc(cs.paddingLeft) * (/^inline-/.test(cs.display) ? 1 : 0) >= 3 && last && !/ $/.test(last.t)) last.t += ' ';
        [...n.childNodes].forEach(walk);
        if (pc(cs.marginRight) >= 3) runs.push({ t: ' ', size: pc(cs.fontSize), face: fontFallback, bold: false, italic: false, u: false, color: '000000', alpha: 0, ls: 0, href: null, hl: null, grad: null, sp: 1 });
      }
    };
    nodes.forEach(walk);
    let prevSpace = true;
    for (const r of runs) { if (r.br) { prevSpace = true; continue; } if (prevSpace && !r.pre) r.t = r.t.replace(/^ +/, ''); prevSpace = / $/.test(r.t); }
    for (let i = runs.length - 1, nextBr = true; i >= 0; i--) { const r = runs[i]; if (r.br) { nextBr = true; continue; } if (nextBr) { r.t = r.t.replace(/ +$/, ''); if (r.t) nextBr = false; } }
    return runs.filter(r => r.br || r.t);
  };
  let pendingBullet = null;
  const bulletOf = (el, cs) => {
    if (cs.display !== 'list-item' || cs.listStyleType === 'none') return null;
    const mk = getComputedStyle(el, '::marker');
    const t = cs.listStyleType.replace(/^["']|["']$/g, '');
    const NUM = { decimal: 'arabicPeriod', 'decimal-leading-zero': 'arabicPeriod', 'lower-alpha': 'alphaLcPeriod', 'lower-latin': 'alphaLcPeriod', 'upper-alpha': 'alphaUcPeriod', 'upper-latin': 'alphaUcPeriod', 'lower-roman': 'romanLcPeriod', 'upper-roman': 'romanUcPeriod' };
    const CH = { disc: '\u2022', circle: '\u25E6', square: '\u25AA', 'disclosure-closed': '\u25B8', 'disclosure-open': '\u25BE' };
    const fsz = pc(cs.fontSize);
    const bul = { indent: fsz * 1.15, color: (rgba(mk.color) || rgba(cs.color) || {}).hex };
    if (NUM[t]) {
      const list = el.parentElement; const lis = [...list.children].filter(c => getComputedStyle(c).display === 'list-item');
      bul.type = 'number'; bul.numberType = NUM[t]; bul.start = el.value > 0 ? el.value : (list.start || 1) + lis.indexOf(el);
      bul.indent = fsz * 1.6;
    } else bul.char = CH[t] || t.trim().slice(0, 2) || '\u2022';
    return bul;
  };
  const textItem = (rect, runs, cs, opa, el) => {
    if (!runs.some(r => r.t && /\S/.test(r.t))) return;
    if (el && cs.textOverflow === 'ellipsis' && el.scrollWidth > el.clientWidth + 2) {
      let keep = Math.floor(runs.reduce((a, r) => a + (r.t ? r.t.length : 0), 0) * el.clientWidth / el.scrollWidth) - 2;
      for (const r of runs) { if (!r.t) continue; if (keep <= 0) { r.t = ''; continue; } if (r.t.length > keep) { r.t = r.t.slice(0, keep).replace(/\s+\S*$/, '') + '…'; keep = 0; } else keep -= r.t.length; }
      runs = runs.filter(r => r.br || r.t);
    }
    const fs0 = runs.find(r => r.t)?.size || pc(cs.fontSize);
    const lh = cs.lineHeight === 'normal' ? fs0 * 1.33 : pc(cs.lineHeight);
    let align = cs.textAlign; if (align === 'start') align = 'left'; if (align === 'end') align = 'right'; if (align === 'justify') align = 'left';
    let valign = 'top';
    if (/flex/.test(cs.display)) {
      if (cs.flexDirection.startsWith('row')) { if (cs.alignItems === 'center') valign = 'middle'; if (cs.justifyContent === 'center') align = 'center'; }
      else { if (cs.justifyContent === 'center') valign = 'middle'; if (cs.alignItems === 'center') align = 'center'; }
    }
    let bullet = null;
    if (pendingBullet) { bullet = pendingBullet.bul; rect = { ...rect, x: Math.min(rect.x, pendingBullet.x), w: rect.w + Math.max(0, rect.x - pendingBullet.x) }; pendingBullet = null; }
    items.push({ t: 'text', ...rect, runs, lh, align, valign, opa, lines: Math.max(1, Math.round(rect.h / lh)), pre: /pre/.test(cs.whiteSpace), bullet });
  };
  const contentBox = (el, cs) => {
    const r = box(el.getBoundingClientRect());
    const l = pc(cs.paddingLeft) + pc(cs.borderLeftWidth), t = pc(cs.paddingTop) + pc(cs.borderTopWidth);
    const rr = pc(cs.paddingRight) + pc(cs.borderRightWidth), b = pc(cs.paddingBottom) + pc(cs.borderBottomWidth);
    return { x: r.x + l, y: r.y + t, w: Math.max(1, r.w - l - rr), h: Math.max(1, r.h - t - b) };
  };
  const rangeBox = nodes => {
    const rg = document.createRange(); rg.setStartBefore(nodes[0]); rg.setEndAfter(nodes[nodes.length - 1]);
    const rs = [...rg.getClientRects()].filter(r => r.width > 0 && r.height > 0);
    if (!rs.length) return null;
    const L = Math.min(...rs.map(r => r.left)), T = Math.min(...rs.map(r => r.top)), Rr = Math.max(...rs.map(r => r.right)), B = Math.max(...rs.map(r => r.bottom));
    return box({ left: L, top: T, width: Rr - L, height: B - T });
  };
  const addRaster = (el, mode, margin, extra) => {
    if (el.hasAttribute('data-rxid')) return;
    const id = sid + '_' + (rx++);
    el.setAttribute('data-rxid', id);
    const r = box(el.getBoundingClientRect());
    rasters.push({ id, mode, margin });
    items.push({ t: 'img', file: id + '.png', x: r.x - margin, y: r.y - margin, w: r.w + 2 * margin, h: r.h + 2 * margin, ...(extra || {}) });
  };

  // video players: the <video> or its closest player wrapper
  S.querySelectorAll('video').forEach(v => {
    let p = playerSel ? v.closest(playerSel) : null;
    if (!p || !S.contains(p)) {
      p = v; const vr = v.getBoundingClientRect();
      for (let a = v.parentElement; a && a !== S; a = a.parentElement) {
        const ar = a.getBoundingClientRect();
        if (vr.width * vr.height < 0.55 * ar.width * ar.height) break;
        if (/player|video/i.test(typeof a.className === 'string' ? a.className : '')) p = a;
      }
    }
    p.setAttribute('data-h2p-player', '1');
    p.__h2pVideo = v;
  });
  const cuesOf = p => {
    const host = p.closest('[data-cues]') || p.querySelector('[data-cues]');
    if (host) { try { return { cues: JSON.parse(host.getAttribute('data-cues')) }; } catch (e) { /* ignore */ } }
    const tr = p.querySelector('track[kind="captions"], track[kind="subtitles"], track');
    return tr ? { track: new URL(tr.getAttribute('src'), location.href).href } : {};
  };

  const visit = (el, opa) => {
    if (el.nodeType !== 1 || SKIPTAG.has(el.tagName) || isNotes(el)) return;
    const cs = getComputedStyle(el);
    if (hidden(el, cs)) return;
    const o = opa * (+cs.opacity);
    const r0 = el.getBoundingClientRect();
    if (r0.width < 0.5 && r0.height < 0.5 && cs.overflow !== 'visible') return;
    const tag = el.tagName.toLowerCase();

    if (el.hasAttribute('data-h2p-player')) {
      const v = el.__h2pVideo || el.querySelector('video');
      const raw = v.currentSrc || v.getAttribute('src') || v.querySelector('source')?.getAttribute('src') || v.getAttribute('data-video') || v.getAttribute('data-src');
      const id = sid + '_v' + (rx++);
      v.setAttribute('data-rxid', id);
      rasters.push({ id, mode: 'deep', margin: 0, cover: true });
      items.push({ t: 'video', id, ...box(r0), vid: box(v.getBoundingClientRect()), src: raw ? new URL(raw, location.href).href : null, bg: rgba(cs.backgroundColor), rad: pc(cs.borderTopLeftRadius), ...cuesOf(el) });
      return;
    }
    if (tag === 'svg' || tag === 'img' || tag === 'canvas' || tag === 'iframe' || tag === 'video' || tag === 'picture' || tag === 'object') {
      if (cs.mixBlendMode !== 'normal' || (cs.webkitMaskImage && cs.webkitMaskImage !== 'none' && tag === 'img')) { el.setAttribute('data-bake', '1'); return; }
      if (r0.width < 1 || r0.height < 1) return;
      const extra = {};
      const a = el.closest('a[href]'); if (a) extra.href = a.getAttribute('href');
      if (tag === 'img') extra.alt = el.getAttribute('alt') || '';
      addRaster(el, 'deep', tag === 'svg' ? 2 : 0, extra);
      return;
    }
    if (tag === 'table') { tableItem(el, o); return; }

    const bg = rgba(cs.backgroundColor);
    const bi = cs.backgroundImage !== 'none' ? cs.backgroundImage : null;
    const lin = bi ? parseLinear(bi) : null;
    const clipText = cs.webkitBackgroundClip === 'text' || cs.backgroundClip === 'text';
    const bws = ['Top', 'Right', 'Bottom', 'Left'].map(s => pc(cs['border' + s + 'Width']));
    const bcs = ['Top', 'Right', 'Bottom', 'Left'].map(s => rgba(cs['border' + s + 'Color']));
    const hasBorder = bws.some((w, i) => w > 0 && bcs[i] && cs['border' + ['Top', 'Right', 'Bottom', 'Left'][i] + 'Style'] !== 'none');
    const sh = shadowOf(cs);
    const pb = visiblePseudo(el, '::before'), pa = visiblePseudo(el, '::after');
    const pRaster = (pb && pb.kind === 'raster') || (pa && pa.kind === 'raster');
    const fx = (cs.filter && cs.filter !== 'none') || (cs.webkitMaskImage && cs.webkitMaskImage !== 'none') || (cs.transform && cs.transform !== 'none' && !/matrix\(1, 0, 0, 1/.test(cs.transform)) || (cs.clipPath && cs.clipPath !== 'none');
    const paints = (!clipText && (bg || bi)) || hasBorder || sh || pb || pa;
    if (paints && el !== S) {
      const r = box(r0);
      const native = !fx && !pRaster && (!bi || lin) && !(bi && clipText);
      if (native) {
        const rr0 = cs.borderTopLeftRadius; const rad = Math.min(/%/.test(rr0) ? pc(rr0) / 100 * Math.min(r.w, r.h) : pc(rr0), r.w / 2, r.h / 2);
        const oval = rad >= Math.min(r.w, r.h) / 2 - 0.5 && Math.abs(r.w - r.h) < 2;
        const pseudoB = [pb, pa].find(p => p && p.kind === 'border');
        const uniform = bws.every((w, i) => w === bws[0] && (!w || (bcs[i] && bcs[0] && bcs[i].hex === bcs[0].hex)));
        const line = pseudoB ? { w: pseudoB.w, c: pseudoB.c, grad: pseudoB.grad || null } : (hasBorder && uniform ? { w: bws[0], c: bcs[0], dash: cs.borderTopStyle === 'dashed' || cs.borderTopStyle === 'dotted' } : null);
        items.push({ t: 'shape', ...r, rad, oval, fill: clipText ? null : (lin ? null : bg), grad: clipText ? null : lin, line, sh, opa: o });
        if (hasBorder && !uniform) {
          const [T, Rg, B, L] = bws;
          if (T && bcs[0]) items.push({ t: 'shape', x: r.x, y: r.y, w: r.w, h: T, rad: 0, fill: bcs[0], opa: o });
          if (B && bcs[2]) items.push({ t: 'shape', x: r.x, y: r.y + r.h - B, w: r.w, h: B, rad: 0, fill: bcs[2], opa: o });
          if (L && bcs[3]) items.push({ t: 'shape', x: r.x, y: r.y, w: L, h: r.h, rad: 0, fill: bcs[3], opa: o });
          if (Rg && bcs[1]) items.push({ t: 'shape', x: r.x + r.w - Rg, y: r.y, w: Rg, h: r.h, rad: 0, fill: bcs[1], opa: o });
        }
      } else {
        addRaster(el, 'shell', (pRaster || sh) ? 40 : 2);
      }
    }

    const bul = bulletOf(el, cs);
    if (bul) pendingBullet = { bul, x: contentBox(el, cs).x };
    const kids = [...el.childNodes];
    if (hasText(el) && kids.every(isInline)) {
      const cb = contentBox(el, cs);
      const rb = rangeBox(kids);
      if (rb && rb.h > (cs.lineHeight === 'normal' ? pc(cs.fontSize) * 1.5 : pc(cs.lineHeight) * 1.5) && rb.w < cb.w - 4) {
        if (/start|left|justify/.test(cs.textAlign)) cb.w = rb.w + 6;
        else if (cs.textAlign === 'center') { cb.x = rb.x - 3; cb.w = rb.w + 6; }
      }
      if (pendingBullet) cb.x = pendingBullet.x;
      textItem(cb, runsOf(kids, el), cs, o, el);
      pendingBullet = null;
      return;
    }
    let group = [];
    const flush = () => {
      if (group.some(n => hasText(n))) { const rb = rangeBox(group); if (rb) textItem({ x: rb.x - 1, y: rb.y, w: rb.w + 2, h: rb.h }, runsOf(group, el), cs, o); }
      group = [];
    };
    for (const n of kids) {
      if (isInline(n)) group.push(n);
      else { flush(); visit(n, o); }
    }
    flush();
  };

  // width check for substituted fonts: measure with the real CSS font and with a locally installed proxy of the target
  const cvs = document.createElement('canvas').getContext('2d');
  const installed = f => { cvs.font = `72px "${f}", monospace`; const a = cvs.measureText('mmmmmlli1WQ').width; cvs.font = '72px monospace'; return a !== cvs.measureText('mmmmmlli1WQ').width; };
  const proxyOf = face => installed(face) ? face : /consol|courier|mono/i.test(face) ? 'Courier New' : /georgia|palatino|garamond|times|cambria|book antiqua|constantia/i.test(face) ? 'Georgia' : 'Arial';
  const fitScale = (cell, cs, availW) => {
    const runs = cell.paras.flat().filter(r => r.t);
    if (!runs.length) return 1;
    let orig = 0, sub = 0;
    for (const r of runs) {
      const st = `${r.italic ? 'italic ' : ''}${r.bold ? 700 : 400} ${r.size}px `;
      cvs.font = st + cs.fontFamily; orig += cvs.measureText(r.t).width;
      cvs.font = st + `"${proxyOf(r.face)}"`; sub += cvs.measureText(r.t).width;
    }
    const need = Math.max(orig, sub * (/segoe/i.test(runs[0].face) && !installed('Segoe UI') ? 1.04 : 1));
    return need > availW ? Math.max(0.7, availW / need * 0.98) : 1;
  };
  const tableItem = (tbl, o) => {
    const tr = box(tbl.getBoundingClientRect());
    const rows = [...tbl.rows];
    if (!rows.length) return;
    const overlays = [];
    const colW = [...rows[0].cells].map(c => box(c.getBoundingClientRect()).w);
    const rowH = rows.map(r => box(r.getBoundingClientRect()).h);
    const data = rows.map(row => [...row.cells].map(cell => {
      const cs = getComputedStyle(cell);
      const bgc = rgba(cs.backgroundColor) || rgba(getComputedStyle(row).backgroundColor);
      const paras = [], blocks = [];
      let cur = [];
      const ov = [...cell.querySelectorAll('*')].filter(e => { const c = getComputedStyle(e); return (rgba(c.backgroundColor) || c.backgroundImage !== 'none') && c.display !== 'inline'; });
      overlays.push(...ov);
      for (const n of cell.childNodes) {
        if (n.nodeType === 1 && /^(svg|SVG|IMG)$/.test(n.tagName)) continue;
        if (n.nodeType === 1 && ov.some(x => x === n || (n.contains(x) && !n.textContent.replace(x.textContent, '').trim()))) continue;
        if (isInline(n) || (n.nodeType === 1 && getComputedStyle(n).display.includes('inline'))) cur.push(n);
        else { if (cur.length) blocks.push(cur); cur = []; blocks.push([n]); }
      }
      if (cur.length) blocks.push(cur);
      blocks.forEach(b => { const rr = runsOf(b, cell); if (rr.some(r => r.t)) paras.push(rr); });
      const bwB = pc(cs.borderBottomWidth); const bcB = rgba(cs.borderBottomColor);
      const ic = cell.querySelector('svg, img'); const indent = ic && getComputedStyle(ic).float === 'left' ? box(ic.getBoundingClientRect()).w + pc(getComputedStyle(ic).marginRight) : 0;
      const cb = cell.getBoundingClientRect(); const lhC = cs.lineHeight === 'normal' ? pc(cs.fontSize) * 1.3 : pc(cs.lineHeight);
      const avail = cb.width / sc - pc(cs.paddingLeft) - pc(cs.paddingRight) - indent - 2;
      const scale = paras.length === 1 && (cb.height / sc - pc(cs.paddingTop) - pc(cs.paddingBottom)) < lhC * 1.6 ? fitScale({ paras }, cs, avail) : 1;
      return { scale, indent, paras, fill: bgc, align: /center/.test(cs.textAlign) ? 'center' : /right|end/.test(cs.textAlign) ? 'right' : 'left', valign: cs.verticalAlign === 'top' ? 'top' : cs.verticalAlign === 'bottom' ? 'bottom' : 'middle', pad: [pc(cs.paddingTop), pc(cs.paddingRight), pc(cs.paddingBottom), pc(cs.paddingLeft)], bb: bwB && bcB ? { w: bwB, c: bcB.hex } : null, colspan: cell.colSpan, rowspan: cell.rowSpan };
    }));
    const tcs = getComputedStyle(tbl);
    items.push({ t: 'shape', ...tr, rad: Math.min(pc(tcs.borderTopLeftRadius), 30), fill: rgba(tcs.backgroundColor), sh: shadowOf(tcs), opa: o });
    items.push({ t: 'table', ...tr, colW, rowH, data });
    tbl.querySelectorAll('svg, img').forEach(s => addRaster(s, 'deep', 2));
    overlays.forEach(e => visit(e, o));
  };

  [...S.childNodes].forEach(n => visit(n, 1));
  const nEl = S.querySelector('aside.notes, .notes, .speaker-notes') || document.querySelector(`.notes [data-for="${k + 1}"], [data-note-for="${k + 1}"]`) || (S.id ? document.querySelector(`[data-notes-for="${S.id}"]`) : null);
  const notes = (S.getAttribute('data-notes') || (nEl ? nEl.innerText || nEl.textContent : '') || '').trim();
  const hEl = S.querySelector('h1, h2, [role=heading]');
  const title = ((hEl && (hEl.innerText || hEl.textContent)) || S.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim();
  return { id: sid, htmlId: S.id || null, items, rasters, notes, title, sc, fonts: fontLog };
}

function pageIso({ id, mode, on }) {
  document.querySelectorAll('[data-rxon],[data-rxdeep],[data-rxshell]').forEach(e => { e.removeAttribute('data-rxon'); e.removeAttribute('data-rxdeep'); e.removeAttribute('data-rxshell'); });
  if (!on) { document.documentElement.classList.remove('__iso'); return null; }
  const el = document.querySelector(`[data-rxid="${id}"]`);
  if (!el) return null;
  el.setAttribute('data-rxon', '1');
  if (mode === 'deep') el.setAttribute('data-rxdeep', '1');
  else {
    el.setAttribute('data-rxshell', '1');
    let st = document.getElementById('__h2p_pseudo'); if (!st) { st = document.createElement('style'); st.id = '__h2p_pseudo'; document.head.appendChild(st); }
    st.textContent = ['::before', '::after'].map(w => `[data-rxid="${id}"]${w}{color:${getComputedStyle(el, w).color}!important;-webkit-text-fill-color:${getComputedStyle(el, w).color}!important}`).join('\n');
  }
  document.documentElement.classList.add('__iso');
  const r = el.getBoundingClientRect();
  return { x: r.left, y: r.top, width: r.width, height: r.height };
}

const rectOf = k => { const S = document.querySelector(`[data-h2p-slide="${k}"]`); const r = (S.closest('[data-h2p-frame]') || S).getBoundingClientRect(); return { x: r.left, y: r.top, width: r.width, height: r.height }; };

function isOpaque(buf) {
  try { const png = PNG.sync.read(buf); const d = png.data; for (let i = 3; i < d.length; i += 4 * 7) if (d[i] < 255) return false; return true; } catch { return false; }
}

// ---------- node-side driver ----------
export async function extractDeck(page, o) {
  const log = o.log || (() => {});
  const assets = path.join(o.work, 'assets'); const ref = path.join(o.work, 'ref');
  fs.mkdirSync(assets, { recursive: true }); fs.mkdirSync(ref, { recursive: true });
  await page.goto(o.url, { waitUntil: 'load' });
  await page.evaluate(() => document.fonts && document.fonts.ready);
  await page.waitForTimeout(o.settle * 2);
  let det = await page.evaluate(pageDetect, { selector: o.selector, auto: AUTO_SELECTORS });
  if (!det.count) throw new Error(`No slides found${o.selector ? ` for selector "${o.selector}"` : ''}. Pass --selector.`);
  let W = o.width || det.w, H = o.height || det.h;
  if (!W || !H || W < 200 || H < 150) { W = 1600; H = 900; }
  const vp = page.viewportSize();
  if (vp.width !== W || vp.height !== H) {
    await page.setViewportSize({ width: W, height: H });
    await page.waitForTimeout(o.settle);
    det = await page.evaluate(pageDetect, { selector: det.selector, auto: AUTO_SELECTORS });
    if (!o.width) { W = det.w || W; H = det.h || H; }
  }
  log(`slides: ${det.count} via "${det.selector}", design size ${W}x${H}`);
  await page.addStyleTag({ content: BASE_CSS });
  await page.evaluate(b => { document.documentElement.classList.add('__h2p'); if (b) document.documentElement.classList.add('__h2p_builds'); }, o.builds);

  const only = o.slides ? new Set(o.slides) : null;
  const plan = [];
  let kb = -1;
  for (let k = 0; k < det.count; k++) {
    if (only && !only.has(k + 1)) continue;
    let mode = 'native';
    await page.evaluate(pageShow, k);
    await page.waitForTimeout(o.settle);
    if (!(await page.evaluate(pageVisible, k))) {
      // scrolling decks: scroll the document only (scrollIntoView would also scroll overflow:hidden stages)
      const moved = await page.evaluate(k => { const S = document.querySelector(`[data-h2p-slide="${k}"]`); const se = document.scrollingElement; if (se.scrollHeight <= innerHeight + 2 && se.scrollWidth <= innerWidth + 2) return false; const r = S.getBoundingClientRect(); scrollTo(scrollX + r.left, scrollY + r.top); return true; }, k);
      if (moved) { mode = 'scroll'; await page.waitForTimeout(o.settle); }
    }
    if (!(await page.evaluate(pageVisible, k))) {
      // keyboard navigation (most custom decks): Home, then ArrowRight until the slide shows
      mode = 'keys';
      if (kb < 0 || kb > k) { await page.keyboard.press('Home'); await page.waitForTimeout(o.settle); kb = 0; }
      for (let tries = 0; !(await page.evaluate(pageVisible, k)) && tries < (k - kb) + 12; tries++) { await page.keyboard.press('ArrowRight'); await page.waitForTimeout(Math.max(120, o.settle / 2)); }
      if (await page.evaluate(pageVisible, k)) kb = k;
      else { mode = 'forced'; const n = await page.evaluate(pageForce, { k, W, H }); if (n) mode += `(+${n} hidden builds shown)`; await page.waitForTimeout(o.settle); }
    }
    await page.evaluate(pageChrome, { k, hide: o.hide || null });
    // wait until the slide frame stops moving/scaling and has the design aspect ratio
    let R = await page.evaluate(rectOf, k);
    for (let t = 0; t < 25; t++) {
      await page.waitForTimeout(100);
      const R2 = await page.evaluate(rectOf, k);
      const same = ['x', 'y', 'width', 'height'].every(p => Math.abs(R2[p] - R[p]) < 0.5);
      R = R2;
      if (same && Math.abs(R.width / R.height - W / H) < 0.02 * (W / H)) break;
    }
    await page.screenshot({ path: path.join(ref, `${String(k + 1).padStart(2, '0')}.png`), clip: R });
    const res = await page.evaluate(pageExtract, { k, fontMap: o.fontMap, fontFallback: o.fontFallback, playerSel: o.playerSelector || null, keepFonts: !!o.keepFonts });
    res.mode = mode;
    res.textCount = res.items.filter(i => i.t === 'text').length;
    const sc = res.sc;

    await page.evaluate(() => document.documentElement.classList.add('__bg'));
    await page.waitForTimeout(60);
    await page.screenshot({ path: path.join(assets, `${res.id}__bg.jpg`), type: 'jpeg', quality: 90, clip: R });
    await page.evaluate(() => document.documentElement.classList.remove('__bg'));

    for (const ra of res.rasters) {
      const clip = await page.evaluate(pageIso, { id: ra.id, mode: ra.mode, on: true });
      if (!clip) { ra.err = 'missing'; continue; }
      const m = ra.margin;
      const c = { x: Math.max(0, clip.x - m * sc), y: Math.max(0, clip.y - m * sc), width: clip.width + 2 * m * sc, height: clip.height + 2 * m * sc };
      c.width = Math.min(c.width, W - c.x); c.height = Math.min(c.height, H - c.y);
      if (c.width < 1 || c.height < 1) { ra.err = 'offscreen'; await page.evaluate(pageIso, { on: false }); continue; }
      try {
        const buf = await page.screenshot({ omitBackground: true, clip: c });
        let file = ra.id + '.png';
        if (ra.cover || (buf.length > 120000 && isOpaque(buf))) { file = ra.id + '.jpg'; await page.screenshot({ path: path.join(assets, file), type: 'jpeg', quality: 88, clip: c }); }
        else fs.writeFileSync(path.join(assets, file), buf);
        const it = res.items.find(x => x.file === ra.id + '.png');
        if (it) { it.file = file; it.x = (c.x - R.x) / sc; it.y = (c.y - R.y) / sc; it.w = c.width / sc; it.h = c.height / sc; }
        const vit = res.items.find(x => x.t === 'video' && x.id === ra.id);
        if (vit) vit.cover = file;
      } catch (e) { ra.err = String(e).slice(0, 120); }
      await page.evaluate(pageIso, { on: false });
    }
    const errs = res.rasters.filter(r => r.err).length;
    log(`  ${res.id} [${mode}] items ${res.items.length} rasters ${res.rasters.length}${errs ? ` (${errs} failed)` : ''}${res.title ? ' — ' + res.title.slice(0, 60) : ''}`);
    plan.push(res);
  }
  return { W, H, selector: det.selector, slides: plan };
}

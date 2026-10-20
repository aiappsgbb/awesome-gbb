// Build a native, editable PPTX from the extracted plan with pptxgenjs.
import fs from 'node:fs';
import path from 'node:path';
import pptxgen from 'pptxgenjs';

const alpha2tr = a => Math.round((1 - Math.max(0, Math.min(1, a))) * 100);
const hex4 = (p, i) => p + (1000 + i).toString(16).toUpperCase().padStart(4, '0');

export async function buildPptx(deck, o) {
  const { W, H, slides } = deck;
  const SW = 13.333, SH = +(SW * H / W).toFixed(3);
  const PX = SW / W;               // css px -> inches
  const FPT = SW * 72 / W;         // css px -> points
  const in_ = v => +(v * PX).toFixed(4);
  const A = path.join(o.work, 'assets');

  const pres = new pptxgen();
  if (Math.abs(SH - 7.5) < 0.01) pres.layout = 'LAYOUT_WIDE';
  else { pres.defineLayout({ name: 'DECK', width: SW, height: SH }); pres.layout = 'DECK'; }
  if (o.title) pres.title = o.title;
  if (o.author) pres.author = o.author;
  if (o.company) pres.company = o.company;
  if (o.subject) pres.subject = o.subject;

  const slideIndex = {};
  slides.forEach((p, i) => { if (p.htmlId) slideIndex[p.htmlId] = i + 1; });
  const GRAD = [], GLN = [], GRADTEXT = [], GSENT = [];
  const gradSentinel = g => { const k = JSON.stringify(g); let i = GSENT.findIndex(x => x.k === k); if (i < 0) { GSENT.push({ k, g }); i = GSENT.length - 1; } return hex4('FE', i); };
  const link = href => {
    if (!href) return null;
    if (href.startsWith('#')) { const t = slideIndex[decodeURIComponent(href.slice(1))]; return t ? { slide: t } : null; }
    if (/^(https?:|mailto:)/i.test(href)) return { url: href };
    return null;
  };

  function addShape(s, it, si) {
    const opts = {
      x: in_(it.x), y: in_(it.y), w: in_(Math.max(it.w, 0.5)), h: in_(Math.max(it.h, 0.5)),
      line: it.line && it.line.c ? { color: it.line.grad ? hex4('FD', GLN.length) : it.line.c.hex, width: Math.max(0.25, it.line.w * FPT), transparency: alpha2tr(it.line.c.a * it.opa), dashType: it.line.dash ? 'dash' : 'solid' } : { type: 'none' },
    };
    const shapeType = it.oval ? pres.shapes.OVAL : it.rad > 1 ? pres.shapes.ROUNDED_RECTANGLE : pres.shapes.RECTANGLE;
    if (it.rad > 1 && !it.oval) opts.rectRadius = Math.min(in_(it.rad), Math.min(in_(it.w), in_(it.h)) / 2);
    if (it.line && it.line.c && it.line.grad) GLN.push({ col: hex4('FD', GLN.length), g: it.line.grad });
    if (it.grad) {
      const name = `GRAD_${si}_${GRAD.length}`;
      GRAD.push({ name, ang: it.grad.ang, stops: it.grad.stops, opa: it.opa });
      opts.fill = { color: it.grad.stops[0].c };
      opts.objectName = name;
    } else if (it.fill) opts.fill = { color: it.fill.hex, transparency: alpha2tr(it.fill.a * it.opa) };
    else opts.fill = { type: 'none' };
    if (it.sh && it.sh.op >= 0.05 && (it.fill || it.grad)) {
      const off = Math.hypot(it.sh.ox, it.sh.oy);
      opts.shadow = { type: 'outer', color: it.sh.c, blur: Math.min(40, it.sh.blur * FPT * 0.7), offset: off * FPT, angle: off ? Math.round((Math.atan2(it.sh.oy, it.sh.ox) * 180 / Math.PI + 360) % 360) : 90, opacity: Math.min(0.35, it.sh.op * 0.8) };
    }
    if (!it.grad && it.fill && it.fill.a * it.opa < 0.02 && !(it.line && it.line.c)) return;
    if (!it.grad && !it.fill && !(it.line && it.line.c)) return;
    s.addShape(shapeType, opts);
  }

  function runOpts(r, base) {
    const ro = { fontFace: r.face, fontSize: +Math.max(1, r.size * FPT).toFixed(1), bold: r.bold, italic: r.italic, color: r.grad ? gradSentinel(r.grad) : r.color };
    if (r.grad) ro.__grad = r.grad;
    if (r.alpha < 0.98 || (base && base.opa < 0.98)) ro.transparency = alpha2tr(r.alpha * (base ? base.opa : 1));
    if (r.u) ro.underline = { style: 'sng' };
    if (r.strike) ro.strike = 'sngStrike';
    if (r.sup) ro.superscript = true;
    if (r.sub) ro.subscript = true;
    if (r.ls) ro.charSpacing = +(r.ls * FPT).toFixed(1);
    const l = link(r.href); if (l) ro.hyperlink = l;
    if (r.hl) ro.highlight = r.hl;
    return ro;
  }

  function addText(s, it, si) {
    const arr = [];
    it.runs.forEach(r => {
      if (r.br) { if (arr.length) arr[arr.length - 1].options.breakLine = true; return; }
      arr.push({ text: r.t, options: runOpts(r, it) });
    });
    if (!arr.length) return;
    const fs0 = it.runs.find(r => r.t).size;
    const pad = 2;
    // PowerPoint removes the space above the first line when line spacing < 100%; CSS keeps half-leading
    const dy = 0.75 * Math.max(0, 1.33 * fs0 - it.lh);
    const multi = it.lines > 1 || it.runs.some(r => r.br);
    const opts = {
      x: in_(it.x - pad - (it.lines > 1 && it.align === 'center' ? it.w * 0.02 : 0)), y: in_(it.y + dy), w: in_(it.w * (it.lines > 1 && !it.pre ? 1.04 : 1) + 2 * pad), h: in_(Math.max(it.h, it.lh)),
      margin: 0, align: it.align, valign: it.valign === 'middle' ? 'middle' : 'top',
      fit: 'none', wrap: multi,
      lineSpacingMultiple: +Math.max(0.8, Math.min(1.6, (it.lh / fs0) / 1.33)).toFixed(2),
      paraSpaceBefore: 0, paraSpaceAfter: 0,
    };
    if (!multi) {
      // single line: centre the PowerPoint line on the CSS line box (font-metric independent, like CSS half-leading)
      const ly = it.valign === 'middle' ? it.y + (it.h - it.lh) / 2 : it.y;
      opts.y = in_(ly); opts.h = in_(it.lh); opts.valign = 'middle'; delete opts.lineSpacingMultiple;
    }
    if (it.bullet) {
      const ind = it.bullet.indent;
      opts.x = in_(it.x - ind - pad); opts.w = +(opts.w + in_(ind)).toFixed(4);
      const bo = it.bullet.type === 'number' ? { type: 'number', numberType: it.bullet.numberType, numberStartAt: it.bullet.start, indent: +(ind * FPT).toFixed(1) } : { code: it.bullet.char.codePointAt(0).toString(16).toUpperCase().padStart(4, '0'), indent: +(ind * FPT).toFixed(1) };
      arr[0].options.bullet = bo;
    }
    const allGrad = arr.every(a => a.options.__grad || !/\S/.test(a.text));
    if (!allGrad) arr.forEach(a => { if (a.options.__grad) { const st = a.options.__grad.stops; a.options.color = st[Math.min(st.length - 1, 1)].c; delete a.options.__grad; } });
    if (arr.some(a => a.options.__grad)) {
      const name = `GTXT_${si}_${GRADTEXT.length}`;
      GRADTEXT.push({ name, grad: arr.find(a => a.options.__grad).options.__grad });
      opts.objectName = name;
    }
    arr.forEach(a => delete a.options.__grad);
    s.addText(arr, opts);
  }

  function addTable(s, it) {
    const rows = it.data.map(row => row.map(cell => {
      const paras = [];
      cell.paras.forEach((pr, pi) => {
        pr.forEach(r => {
          if (r.br) { if (paras.length) paras[paras.length - 1].options.breakLine = true; return; }
          const ro = runOpts(cell.scale && cell.scale < 1 ? { ...r, size: r.size * cell.scale } : r, { opa: 1 }); delete ro.__grad;
          if (r.grad) ro.color = r.grad.stops[1].c;
          paras.push({ text: r.t, options: ro });
        });
        if (pi < cell.paras.length - 1 && paras.length) paras[paras.length - 1].options.breakLine = true;
      });
      const co = {
        fill: cell.fill ? { color: cell.fill.hex, transparency: alpha2tr(cell.fill.a) } : undefined,
        margin: cell.pad.map((v, i) => +((v + (i === 3 ? cell.indent || 0 : 0)) * FPT).toFixed(1)),
        valign: cell.valign, align: cell.align,
        border: [{ type: 'none' }, { type: 'none' }, cell.bb ? { type: 'solid', pt: Math.max(0.5, cell.bb.w * FPT), color: cell.bb.c } : { type: 'none' }, { type: 'none' }],
      };
      if (cell.colspan > 1) co.colspan = cell.colspan;
      if (cell.rowspan > 1) co.rowspan = cell.rowspan;
      return { text: paras.length ? paras : '', options: co };
    }));
    s.addTable(rows, { x: in_(it.x), y: in_(it.y), w: in_(it.w), colW: it.colW.map(in_), rowH: it.rowH.map(in_), autoPage: false });
  }

  function addImage(s, it) {
    const f = path.join(A, it.file);
    if (!fs.existsSync(f)) return;
    const io = { path: f, x: in_(it.x), y: in_(it.y), w: in_(it.w), h: in_(it.h), altText: it.alt || '' };
    const l = link(it.href); if (l) io.hyperlink = l;
    s.addImage(io);
  }

  function addVideo(s, it) {
    const box = it.burned ? { x: it.x, y: it.y, w: it.w, h: it.h } : it.vid;
    let { x, y, w, h } = box;
    if (it.ar) { let ww = w, hh = w / it.ar; if (hh > h) { hh = h; ww = h * it.ar; } x += (w - ww) / 2; y += (h - hh) / 2; w = ww; h = hh; }
    if (it.bg) s.addShape(it.rad > 1 ? pres.shapes.ROUNDED_RECTANGLE : pres.shapes.RECTANGLE, { x: in_(it.x), y: in_(it.y), w: in_(it.w), h: in_(it.h), ...(it.rad > 1 ? { rectRadius: Math.min(in_(it.rad), in_(Math.min(it.w, it.h)) / 2) } : {}), fill: { color: it.bg.hex, transparency: alpha2tr(it.bg.a) }, line: { type: 'none' } });
    const cover = it.cover && fs.existsSync(path.join(A, it.cover)) ? path.join(A, it.cover) : null;
    if (!it.file || o.noVideo) { if (cover) s.addImage({ path: cover, x: in_(it.vid.x), y: in_(it.vid.y), w: in_(it.vid.w), h: in_(it.vid.h) }); return; }
    const mo = { type: 'video', path: it.file, x: in_(x), y: in_(y), w: in_(w), h: in_(h) };
    if (cover) mo.cover = `data:image/${/\.png$/.test(cover) ? 'png' : 'jpeg'};base64,` + fs.readFileSync(cover).toString('base64');
    s.addMedia(mo);
  }

  const failures = [];
  slides.forEach((p, si) => {
    const s = pres.addSlide();
    s.background = { path: path.join(A, `${p.id}__bg.jpg`) };
    for (const it of p.items) {
      try {
        if (it.t === 'shape') addShape(s, it, si);
        else if (it.t === 'text') addText(s, it, si);
        else if (it.t === 'img') addImage(s, it);
        else if (it.t === 'table') addTable(s, it);
        else if (it.t === 'video') addVideo(s, it);
      } catch (e) { failures.push(`${p.id} ${it.t}: ${e.message}`); }
    }
    if (p.notes) s.addNotes(p.notes);
  });
  const grad = { lines: GLN, shapes: GRAD, text: GRADTEXT, sent: GSENT.map((x, i) => ({ col: hex4('FE', i), g: x.g })) };
  const buf = await pres.write({ outputType: 'nodebuffer' });
  return { buf, grad, failures, size: { SW, SH } };
}

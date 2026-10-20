// Post-process the pptxgenjs output: inject native gradients (fills, borders, text) and deduplicate media.
import crypto from 'node:crypto';
import JSZip from 'jszip';

function gsfill(g, opa = 1) {
  const oang = Math.round((((g.ang - 90) % 360) + 360) % 360 * 60000);
  const gs = g.stops.map(s => `<a:gs pos="${Math.round(s.p * 1000)}"><a:srgbClr val="${s.c}">${s.a * opa < 0.999 ? `<a:alpha val="${Math.round(s.a * opa * 100000)}"/>` : ''}</a:srgbClr></a:gs>`).join('');
  return `<a:gradFill rotWithShape="1"><a:gsLst>${gs}</a:gsLst><a:lin ang="${oang}" scaled="0"/></a:gradFill>`;
}

export async function postProcess(buf, grad) {
  const zip = await JSZip.loadAsync(buf);
  const shapeBy = Object.fromEntries(grad.shapes.map(g => [g.name, g]));
  const textBy = Object.fromEntries(grad.text.map(g => [g.name, g.grad]));
  let nS = 0, nT = 0;
  for (const f of Object.keys(zip.files).filter(f => /^ppt\/slides\/slide\d+\.xml$/.test(f))) {
    let x = await zip.file(f).async('string');
    x = x.replace(/<p:sp>[\s\S]*?<\/p:sp>/g, sp => {
      const nm = /<p:cNvPr [^>]*name="([^"]+)"/.exec(sp);
      if (!nm) return sp;
      const name = nm[1];
      if (shapeBy[name]) {
        const g = shapeBy[name];
        const sp2 = sp.replace(/(<p:spPr>[\s\S]*?<\/a:prstGeom>)<a:solidFill>[\s\S]*?<\/a:solidFill>/, (m, a) => a + gsfill(g, g.opa ?? 1));
        if (sp2 !== sp) nS++;
        return sp2;
      }
      if (textBy[name]) {
        const g = textBy[name];
        let sp2 = sp.replace(/(<a:rPr[^>]*?)(\/>|>([\s\S]*?)<\/a:rPr>)/g, (m, a, b, inner) => b !== '/>' ? a + '>' + (inner || '').replace(/<a:solidFill>[\s\S]*?<\/a:solidFill>/g, '') + gsfill(g) + '</a:rPr>' : a + '>' + gsfill(g) + '</a:rPr>');
        // gradFill must precede latin/ea/cs/hlinkClick inside rPr
        sp2 = sp2.replace(/<a:rPr([^>]*)>([\s\S]*?)(<a:gradFill[\s\S]*?<\/a:gradFill>)<\/a:rPr>/g, (m, a, b, c) => `<a:rPr${a}>${c}${b}</a:rPr>`);
        nT++;
        return sp2;
      }
      return sp;
    });
    for (const ln of grad.lines) x = x.replace(new RegExp(`<a:solidFill><a:srgbClr val="${ln.col}"(?:/>|>[\\s\\S]*?</a:srgbClr>)</a:solidFill>`, 'g'), gsfill(ln.g));
    for (const s of grad.sent) { const re = new RegExp(`<a:solidFill><a:srgbClr val="${s.col}"/></a:solidFill>`, 'g'); const before = x; x = x.replace(re, gsfill(s.g)); if (x !== before) nT++; }
    zip.file(f, x);
  }

  // deduplicate identical media (pptxgenjs writes one copy per placement)
  const seen = new Map(), rename = new Map();
  for (const f of Object.keys(zip.files).filter(f => f.startsWith('ppt/media/') && !zip.files[f].dir).sort()) {
    const h = crypto.createHash('sha1').update(await zip.file(f).async('nodebuffer')).digest('hex');
    if (seen.has(h)) { rename.set(f.split('/').pop(), seen.get(h).split('/').pop()); zip.remove(f); } else seen.set(h, f);
  }
  if (rename.size) {
    for (const f of Object.keys(zip.files).filter(f => f.endsWith('.rels'))) {
      let x = await zip.file(f).async('string'); let ch = false;
      x = x.replace(/Target="\.\.\/media\/([^"]+)"/g, (m, n) => rename.has(n) ? (ch = true, `Target="../media/${rename.get(n)}"`) : m);
      if (ch) zip.file(f, x);
    }
  }
  const out = await zip.generateAsync({ type: 'nodebuffer', compression: 'DEFLATE', compressionOptions: { level: 6 } });
  return { out, nS, nT, deduped: rename.size };
}

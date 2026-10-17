/* AI Ledger charts: plain SVG, no libraries.
   Four charts, each answering one question:
     forest   - which departments clearly pay off? (return per $1 with its 95% range)
     split    - where does each AI dollar go? (stacked bar)
     index    - did output rise because of AI, or for everyone? (two lines)
     tradeoff - which budget policy is best? (net value against bill risk)
   Rules followed: one axis, thin marks, 2px gaps, direct labels on the story only, a legend whenever there are
   two or more series, hover tooltips that never gate (every value is also in the table view), text in text tokens.
   Colors are the dark steps of the validated categorical palette; gray is the de-emphasis neutral. */
(function () {
  const NS = 'http://www.w3.org/2000/svg';
  const C = { c1: '#3987e5', c2: '#d95926', c3: '#199e70', c4: '#c98500', gray: '#898781',
              surface: '#161b22', grid: '#252c36', axis: '#3a424e', text: '#e6e9ee', mute: '#8b95a5' };
  const usd = n => (n < 0 ? '-' : '') + '$' + Math.abs(Math.round(n)).toLocaleString();
  const usdk = n => Math.abs(n) >= 1000 ? (n < 0 ? '-' : '') + '$' + (Math.abs(n) / 1000).toFixed(Math.abs(n) >= 10000 ? 0 : 1) + 'k' : usd(n);
  const per1 = v => '$' + v.toFixed(2);
  const pct = n => Math.round(n * 100) + '%';

  function el(tag, attrs, text) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs || {}) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    return e;
  }
  function svg(w, h) { const s = el('svg', { viewBox: `0 0 ${w} ${h}`, width: w, height: h, role: 'img' }); s.style.maxWidth = '100%'; s.style.height = 'auto'; return s; }

  // ---- one shared tooltip. Names are untrusted: every string goes in through textContent.
  let tip;
  function tipEl() { if (!tip) { tip = document.createElement('div'); tip.className = 'ctip'; tip.hidden = true; document.body.appendChild(tip); } return tip; }
  function showTip(evt, title, rows) {
    const t = tipEl(); t.replaceChildren();
    const h = document.createElement('div'); h.className = 'ctip-h'; h.textContent = title; t.appendChild(h);
    for (const r of rows) {
      const d = document.createElement('div'); d.className = 'ctip-r';
      if (r.color) { const k = document.createElement('span'); k.className = 'lk'; k.style.background = r.color; d.appendChild(k); }
      const v = document.createElement('b'); v.textContent = r.value; d.appendChild(v);
      const l = document.createElement('span'); l.textContent = ' ' + r.label; d.appendChild(l);
      t.appendChild(d);
    }
    t.hidden = false;
    const x = Math.min(evt.clientX + 14, window.innerWidth - t.offsetWidth - 8), y = Math.min(evt.clientY + 14, window.innerHeight - t.offsetHeight - 8);
    t.style.left = Math.max(8, x) + 'px'; t.style.top = Math.max(8, y) + 'px';
  }
  function hideTip() { if (tip) tip.hidden = true; }
  function hover(node, title, rows) {
    node.setAttribute('tabindex', '0');
    node.addEventListener('pointermove', e => showTip(e, title(), rows()));
    node.addEventListener('pointerleave', hideTip);
    node.addEventListener('focus', () => { const b = node.getBoundingClientRect(); showTip({ clientX: b.left + b.width / 2, clientY: b.top }, title(), rows()); });
    node.addEventListener('blur', hideTip);
  }

  // ---- card shell: title, subtitle, plot, legend, table-view twin
  function shell(host, o) {
    host.replaceChildren();
    const h = document.createElement('h2'); h.textContent = o.title; host.appendChild(h);
    const sub = document.createElement('p'); sub.className = 'note'; sub.style.margin = '-6px 0 8px'; sub.textContent = o.sub; host.appendChild(sub);
    const plot = document.createElement('div'); plot.className = 'plot'; host.appendChild(plot);
    if (o.legend && o.legend.length) {
      const lg = document.createElement('div'); lg.className = 'legend';
      for (const it of o.legend) {
        const s = document.createElement('span'); const k = document.createElement('i'); k.className = it.box ? 'sw' : 'lk'; k.style.background = it.color; s.appendChild(k);
        s.appendChild(document.createTextNode(it.label)); lg.appendChild(s);
      }
      host.appendChild(lg);
    }
    const btn = document.createElement('button'); btn.className = 'ghost tbtn'; btn.textContent = 'Table view'; host.appendChild(btn);
    const tv = document.createElement('div'); tv.hidden = true; tv.className = 'scroll';
    const tb = document.createElement('table');
    const hr = document.createElement('tr'); for (const x of o.headers) { const th = document.createElement('th'); th.textContent = x; hr.appendChild(th); } tb.appendChild(hr);
    for (const row of o.rows) { const tr = document.createElement('tr'); row.forEach((c, i) => { const td = document.createElement('td'); if (i) td.className = 'n'; td.textContent = c; tr.appendChild(td); }); tb.appendChild(tr); }
    tv.appendChild(tb); host.appendChild(tv);
    btn.onclick = () => { const on = tv.hidden; tv.hidden = !on; plot.hidden = on; if (host.querySelector('.legend')) host.querySelector('.legend').hidden = on; btn.textContent = on ? 'Chart view' : 'Table view'; };
    return plot;
  }
  const widthOf = plot => Math.max(300, Math.min(1000, Math.floor(plot.clientWidth || plot.parentElement.clientWidth - 32 || 640)));
  function niceStep(span, n) { const raw = span / n, p = Math.pow(10, Math.floor(Math.log10(raw))), f = raw / p; return (f >= 5 ? 5 : f >= 2 ? 2 : 1) * p; }
  function ticks(lo, hi, n) { const s = niceStep(hi - lo, n); const a = Math.floor(lo / s) * s, out = []; for (let v = a; v <= hi + s * 0.001; v += s) out.push(+v.toFixed(6)); return out; }

  // =====================================================================================
  // 1. Forest plot: dollars back per $1, by department, with the 95% range
  function forest(host, r) {
    const d = Object.entries(r.summary.departments).map(([k, v]) => ({ name: k, p: 1 + v.roi, lo: 1 + v.roi_low, hi: 1 + v.roi_high, conf: v.confidence, verdict: (r.budgets[k] || {}).verdict }))
      .sort((a, b) => b.p - a.p);
    const colorOf = x => x.conf === 'clear' ? (x.p >= 1 ? C.c1 : C.c2) : C.gray;
    const labelOf = x => x.conf === 'clear' ? (x.p >= 1 ? 'Clearly pays off' : 'Clearly does not pay off') : 'Not proven';
    const plot = shell(host, {
      title: 'Which departments clearly pay off?', sub: 'Dollars back for every $1 spent on AI. The line is the 95% range; right of the break-even line is a gain. Gray means the range crosses break-even, so we do not claim more.',
      legend: [{ label: 'Clearly pays off', color: C.c1 }, { label: 'Clearly does not', color: C.c2 }, { label: 'Not proven', color: C.gray }],
      headers: ['Department', 'Back per $1', 'Low', 'High', 'Confidence'],
      rows: d.map(x => [x.name, per1(x.p), per1(x.lo), per1(x.hi), labelOf(x)])
    });
    const W = widthOf(plot), narrow = W < 480, rowH = 38, top = 28, left = narrow ? 84 : 104, right = narrow ? 52 : 70, bottom = 40, H = top + rowH * d.length + bottom;
    // log scale: return per $1 is a ratio, so $0.50 and $2.00 are equally far from break-even
    const g = v => Math.max(v, 0.1);
    const lo = Math.pow(2, Math.floor(Math.log2(Math.min(...d.map(x => g(x.lo)), 0.5)))), hi = Math.pow(2, Math.ceil(Math.log2(Math.max(...d.map(x => x.hi), 2))));
    const X = v => left + (Math.log2(g(v)) - Math.log2(lo)) / (Math.log2(hi) - Math.log2(lo)) * (W - left - right);
    const s = svg(W, H);
    const k0 = Math.round(Math.log2(lo)), k1 = Math.round(Math.log2(hi)), px = (W - left - right) / (k1 - k0), every = Math.max(1, Math.ceil(46 / px));
    for (let k = k0; k <= k1; k++) {
      if (k % every !== 0) continue;  // thin the ticks to what fits; $1.00 (k = 0) always stays
      const t = Math.pow(2, k);
      s.appendChild(el('line', { x1: X(t), x2: X(t), y1: top - 6, y2: H - bottom + 4, stroke: C.grid, 'stroke-width': 1 }));
      s.appendChild(el('text', { x: X(t), y: H - bottom + 20, 'text-anchor': 'middle', fill: C.mute, 'font-size': 11 }, per1(t)));
    }
    s.appendChild(el('line', { x1: X(1), x2: X(1), y1: top - 10, y2: H - bottom + 4, stroke: C.text, 'stroke-opacity': 0.7, 'stroke-width': 1.5 }));
    s.appendChild(el('text', { x: X(1), y: top - 14, 'text-anchor': 'middle', fill: C.text, 'font-size': 11 }, 'break-even $1.00'));
    s.appendChild(el('text', { x: (left + W - right) / 2, y: H - 4, 'text-anchor': 'middle', fill: C.mute, 'font-size': 11 }, 'dollars back per $1 spent (log scale)'));
    s.appendChild(el('text', { x: W - 6, y: top - 14, 'text-anchor': 'end', fill: C.mute, 'font-size': 11 }, 'back per $1'));
    d.forEach((x, i) => {
      const y = top + i * rowH + rowH / 2, col = colorOf(x);
      s.appendChild(el('text', { x: left - 10, y: y + 4, 'text-anchor': 'end', fill: C.text, 'font-size': 12 }, x.name));
      s.appendChild(el('line', { x1: X(x.lo), x2: X(x.hi), y1: y, y2: y, stroke: col, 'stroke-width': 2, 'stroke-linecap': 'round' }));
      for (const e of [x.lo, x.hi]) s.appendChild(el('line', { x1: X(e), x2: X(e), y1: y - 5, y2: y + 5, stroke: col, 'stroke-width': 2 }));
      s.appendChild(el('circle', { cx: X(x.p), cy: y, r: 5, fill: col, stroke: C.surface, 'stroke-width': 2 }));
      s.appendChild(el('text', { x: W - 6, y: y + 4, 'text-anchor': 'end', fill: C.text, 'font-size': 12, 'font-weight': x.conf === 'clear' ? 600 : 400 }, per1(x.p)));  // every row gets its number, in an aligned column
      const hit = el('rect', { x: 0, y: top + i * rowH, width: W, height: rowH, fill: 'transparent' });
      hover(hit, () => x.name, () => [{ color: col, value: per1(x.p), label: 'back per $1' }, { value: per1(x.lo) + ' to ' + per1(x.hi), label: '95% range' }, { value: labelOf(x), label: x.verdict ? '· ' + x.verdict + ' budget' : '' }]);
      s.appendChild(hit);
    });
    plot.appendChild(s);
  }

  // =====================================================================================
  // 2. Where each AI dollar goes: one stacked bar (part to whole)
  function split(host, r) {
    const sp = r.waste.cost_split, total = sp.seats_in_use + sp.seats_unused + sp.tokens_normal + sp.tokens_above_norm;
    const segs = [
      { k: 'seats_in_use', label: 'Seats in use', color: C.c1, ink: '#fff' },
      { k: 'seats_unused', label: 'Seats nobody uses', color: C.c2, ink: '#fff' },
      { k: 'tokens_normal', label: 'Token spend in the normal range', color: C.c3, ink: '#fff' },
      { k: 'tokens_above_norm', label: 'Token spend above peer norms', color: C.c4, ink: '#0b0b0b' }].map(x => ({ ...x, v: sp[x.k] }));
    const lossShare = (sp.seats_unused + sp.tokens_above_norm) / total;
    const plot = shell(host, {
      title: 'Where every AI dollar goes', sub: `${usd(total)} a month in all. ${pct(lossShare)} sits in seats nobody uses or spend above what similar teams use.`,
      legend: segs.map(x => ({ label: `${x.label}: ${usd(x.v)} (${pct(x.v / total)})`, color: x.color, box: true })),
      headers: ['Part', 'Per month', 'Share'], rows: segs.map(x => [x.label, usd(x.v), pct(x.v / total)])
    });
    const W = widthOf(plot), H = 56, left = 4, right = 4, bw = W - left - right, bh = 24, y = 16, gap = 2;
    const s = svg(W, H);
    let x0 = left;
    const round = (x, w, rl, rr) => { const r = 4, x1 = x + w; return `M${x + (rl ? r : 0)},${y} H${x1 - (rr ? r : 0)} ${rr ? `Q${x1},${y} ${x1},${y + r}` : ''} V${y + bh - (rr ? r : 0)} ${rr ? `Q${x1},${y + bh} ${x1 - r},${y + bh}` : ''} H${x + (rl ? r : 0)} ${rl ? `Q${x},${y + bh} ${x},${y + bh - r}` : ''} V${y + (rl ? r : 0)} ${rl ? `Q${x},${y} ${x + r},${y}` : ''} Z`; };
    segs.forEach((g, i) => {
      const w = Math.max(2, g.v / total * bw - (i < segs.length - 1 ? gap : 0));
      const p = el('path', { d: round(x0, w, i === 0, i === segs.length - 1), fill: g.color });
      s.appendChild(p);
      const lbl = usdk(g.v);
      if (w > lbl.length * 7 + 14) s.appendChild(el('text', { x: x0 + w / 2, y: y + bh / 2 + 4, 'text-anchor': 'middle', fill: g.ink, 'font-size': 11, 'font-weight': 600, 'pointer-events': 'none' }, lbl));
      const hit = el('rect', { x: x0, y: y - 8, width: w + gap, height: bh + 16, fill: 'transparent' });
      hover(hit, () => g.label, () => [{ color: g.color, value: usd(g.v), label: 'a month' }, { value: pct(g.v / total), label: 'of AI spend' }]);
      s.appendChild(hit);
      x0 += w + gap;
    });
    plot.appendChild(s);
  }

  // =====================================================================================
  // 3. Output over time: users vs non-users, each person rebased to their own pre-rollout average = 100
  function index(host, r) {
    const ix = r.output_index, m = ix.months, n = m.length;
    const last = i => ix.users[i] - ix.non_users[i];
    const plot = shell(host, {
      title: 'Did output rise because of AI, or for everyone?', sub: `Average output, each person set to 100 in their first ${ix.pre_months} months. Both groups rose (a busy season). Only the gap between the lines is the AI effect.`,
      legend: [{ label: `Using AI (${ix.n_users.toLocaleString()} people)`, color: C.c1 }, { label: `Not using AI (${ix.n_non_users.toLocaleString()} people)`, color: C.c2 }],
      headers: ['Month', 'Using AI', 'Not using AI', 'Gap'], rows: m.map((mo, i) => [mo, ix.users[i].toFixed(1), ix.non_users[i].toFixed(1), (last(i) >= 0 ? '+' : '') + last(i).toFixed(1)])
    });
    const W = widthOf(plot), narrow = W < 520, H = 268, left = 44, right = narrow ? 44 : 116, top = 24, bottom = 30;
    const all = ix.users.concat(ix.non_users).filter(v => v != null);
    const lo = Math.floor((Math.min(...all) - 1) / 5) * 5, hi = Math.ceil((Math.max(...all) + 1) / 5) * 5;
    const X = i => left + i / (n - 1) * (W - left - right), Y = v => top + (1 - (v - lo) / (hi - lo)) * (H - top - bottom);
    const s = svg(W, H);
    s.appendChild(el('rect', { x: X(ix.pre_months), y: top - 4, width: X(n - 1) - X(ix.pre_months) + 8, height: H - top - bottom + 4, fill: C.gray, 'fill-opacity': 0.1 }));
    s.appendChild(el('text', { x: X(ix.pre_months) + 6, y: top + 8, fill: C.mute, 'font-size': 11 }, narrow ? 'rollout' : 'AI rollout (staggered)'));
    for (const t of ticks(lo, hi, 5)) {
      s.appendChild(el('line', { x1: left, x2: W - right + 8, y1: Y(t), y2: Y(t), stroke: C.grid, 'stroke-width': 1 }));
      s.appendChild(el('text', { x: left - 8, y: Y(t) + 4, 'text-anchor': 'end', fill: C.mute, 'font-size': 11 }, t));
    }
    m.forEach((mo, i) => s.appendChild(el('text', { x: X(i), y: H - 8, 'text-anchor': 'middle', fill: C.mute, 'font-size': 11 }, mo.slice(5) + '/' + mo.slice(2, 4))));
    const line = (arr, col) => s.appendChild(el('polyline', { points: arr.map((v, i) => `${X(i)},${Y(v)}`).join(' '), fill: 'none', stroke: col, 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }));
    line(ix.non_users, C.c2); line(ix.users, C.c1);
    for (const [arr, col, name] of [[ix.users, C.c1, 'Using AI'], [ix.non_users, C.c2, 'Not using']]) {
      s.appendChild(el('circle', { cx: X(n - 1), cy: Y(arr[n - 1]), r: 4, fill: col, stroke: C.surface, 'stroke-width': 2 }));
      const ty = name === 'Using AI' ? Y(arr[n - 1]) - 4 : Y(arr[n - 1]) + 14;
      s.appendChild(el('text', { x: X(n - 1) + 12, y: ty, fill: C.text, 'font-size': 12 }, narrow ? arr[n - 1].toFixed(0) : `${name} ${arr[n - 1].toFixed(0)}`));
    }
    const cross = el('line', { y1: top - 4, y2: H - bottom, stroke: C.text, 'stroke-opacity': 0.5, 'stroke-width': 1, visibility: 'hidden' }); s.appendChild(cross);
    m.forEach((mo, i) => {
      const x0 = i === 0 ? left - 12 : (X(i - 1) + X(i)) / 2, x1 = i === n - 1 ? W - right + 12 : (X(i) + X(i + 1)) / 2;
      const hit = el('rect', { x: x0, y: top - 4, width: x1 - x0, height: H - top - bottom + 4, fill: 'transparent' });
      hover(hit, () => mo, () => [{ color: C.c1, value: ix.users[i].toFixed(1), label: 'using AI' }, { color: C.c2, value: ix.non_users[i].toFixed(1), label: 'not using AI' }, { value: (last(i) >= 0 ? '+' : '') + last(i).toFixed(1), label: 'gap' }]);
      hit.addEventListener('pointermove', () => { cross.setAttribute('x1', X(i)); cross.setAttribute('x2', X(i)); cross.setAttribute('visibility', 'visible'); });
      hit.addEventListener('pointerleave', () => cross.setAttribute('visibility', 'hidden'));
      s.appendChild(hit);
    });
    plot.appendChild(s);
  }

  // =====================================================================================
  // 4. Policy trade-off: net value against bill risk
  function tradeoff(host, r) {
    const P = r.policies, rec = 'Variable by role';
    const plot = shell(host, {
      title: 'Which budget policy is best?', sub: 'Higher is more net value. Further left is a more predictable bill. No policy wins on both, so choosing is a trade-off.',
      legend: [{ label: 'Recommended', color: C.c1 }, { label: 'Other policies', color: C.gray }],
      headers: ['Policy', 'Net value / month', 'Bill risk', 'Cost / month'], rows: P.map(p => [p.name, usd(p.net), '+' + pct(p.bill_risk), usd(p.monthly_cost)])
    });
    const W = widthOf(plot), H = 280, left = 62, right = W < 520 ? 70 : 150, top = 22, bottom = 44;
    const xhi = Math.ceil(Math.max(...P.map(p => p.bill_risk * 100)) / 10) * 10 + 10, yhi = Math.ceil(Math.max(...P.map(p => p.net)) / 20000) * 20000 + 10000;
    const ylo = Math.min(0, Math.floor(Math.min(...P.map(p => p.net)) / 20000) * 20000);
    const X = v => left + v / xhi * (W - left - right), Y = v => top + (1 - (v - ylo) / (yhi - ylo)) * (H - top - bottom);
    const s = svg(W, H);
    for (const t of ticks(ylo, yhi, 5)) {
      s.appendChild(el('line', { x1: left, x2: W - right + 6, y1: Y(t), y2: Y(t), stroke: C.grid, 'stroke-width': 1 }));
      s.appendChild(el('text', { x: left - 8, y: Y(t) + 4, 'text-anchor': 'end', fill: C.mute, 'font-size': 11 }, usdk(t)));
    }
    for (const t of ticks(0, xhi, W < 480 ? 3 : 5)) s.appendChild(el('text', { x: X(t), y: H - bottom + 18, 'text-anchor': 'middle', fill: C.mute, 'font-size': 11 }, '+' + t + '%'));
    s.appendChild(el('text', { x: (left + W - right) / 2, y: H - 6, 'text-anchor': 'middle', fill: C.mute, 'font-size': 11 }, W < 480 ? 'bill risk (extra cost at peak)' : 'bill risk: extra cost if everyone spends at their peak month'));
    s.appendChild(el('text', { x: 14, y: (top + H - bottom) / 2, 'text-anchor': 'middle', fill: C.mute, 'font-size': 11, transform: `rotate(-90 14 ${(top + H - bottom) / 2})` }, 'net value per month'));
    const boxes = [], dots = P.map(p => ({ p, x0: X(p.bill_risk * 100) - 9, x1: X(p.bill_risk * 100) + 9, y: Y(p.net) }));
    P.slice().sort((a, b) => a.bill_risk - b.bill_risk).forEach(p => {
      const cx = X(p.bill_risk * 100), cy = Y(p.net), col = p.name === rec ? C.c1 : C.gray, tw = p.name.length * 6.8;
      s.appendChild(el('circle', { cx, cy, r: 6, fill: col, stroke: C.surface, 'stroke-width': 2 }));
      const flip = cx > W - right - 40;
      let lx = flip ? cx - 12 : cx + 12, ly = cy + 4, anchor = flip ? 'end' : 'start';
      let x0 = anchor === 'start' ? lx : lx - tw, x1 = x0 + tw;
      if (boxes.some(b => x0 < b.x1 && x1 > b.x0 && Math.abs(ly - b.y) < 14) || dots.some(d => d.p !== p && x0 < d.x1 && x1 > d.x0 && Math.abs(ly - 4 - d.y) < 10)) {  // label would sit on another label: put it under its dot
        lx = cx; ly = cy + 24; anchor = 'middle'; x0 = lx - tw / 2; x1 = lx + tw / 2;
        if (x0 < left + 6) { anchor = 'start'; lx = left + 8; x0 = lx; x1 = lx + tw; }  // keep labels clear of the axis text
      }
      boxes.push({ x0, x1, y: ly });
      s.appendChild(el('text', { x: lx, y: ly, 'text-anchor': anchor, fill: C.text, 'font-size': 12 }, p.name));
      const hit = el('circle', { cx, cy, r: 18, fill: 'transparent' });
      hover(hit, () => p.name, () => [{ color: col, value: usd(p.net), label: 'net value a month' }, { value: '+' + pct(p.bill_risk), label: 'bill risk' }, { value: usd(p.monthly_cost), label: 'cost a month' }]);
      s.appendChild(hit);
    });
    plot.appendChild(s);
  }

    // =====================================================================================
  // 5. Published evidence: output studies (with your estimate as a band) and time-on-task studies, on separate axes
  const TINY = { 'murphy-hill-2026': 'Microsoft', 'cui-2025': '3 field exps.*', 'brynjolfsson-2023': 'Support', 'dellacqua-2023': 'Consultants',
                 'peng-2023': 'Copilot task', 'paradis-2024': 'Google', 'becker-2025': 'METR' };
  function evidence(host, r) {
    const E = window.EVIDENCE; if (!E) { host.textContent = 'Loading evidence…'; return; }
    const out = E.studies.filter(x => x.metric === 'output').sort((a, b) => b.value - a.value);
    const tim = E.studies.filter(x => x.metric === 'time').sort((a, b) => a.value - b.value);
    const cmp = E.comparison;
    const plot = shell(host, {
      title: 'What published studies found', sub: 'Two different measures, so two separate axes. Gray is a published study; blue is this tool\'s estimate for your data. Context, not proof: the studies differ in setting, tools and who took part. * The range is our own, from the reported standard error.',
      legend: [{ label: 'Published study (line = 95% range where given)', color: '#aab2bd' }, { label: 'Your estimate and its range', color: C.c1 }],
      headers: ['Study', 'Measure', 'Result', 'Range'],
      rows: E.studies.map(x => [x.short + ' (' + x.year + ')', x.measure, x.value == null ? 'see detail' : (x.value > 0 && x.metric === 'output' ? '+' : '') + x.value + '%', x.lo == null ? 'not given' : x.lo.toFixed(1) + '% to ' + x.hi.toFixed(1) + '%'])
    });
    const W = widthOf(plot), narrow = W < 480, gridC = C.grid, right = 56, rowH = 34;
    const name = x => narrow ? TINY[x.id] || x.short : x.short + (x.ci_derived ? '*' : '');
    const left = Math.min(Math.round(W * 0.42), Math.max(narrow ? 84 : 120, Math.max(...E.studies.map(x => name(x).length)) * (narrow ? 6.1 : 6.6) + 22));
    const panel = (title, rows, lo, hi, tickStep, fmt, xlabel, zero, band) => {
      const top = band ? 46 : 34, bottom = 36, H = top + rowH * rows.length + bottom;
      const X = v => left + (v - lo) / (hi - lo) * (W - left - right);
      const s = svg(W, H);
      s.appendChild(el('text', { x: 4, y: 14, fill: C.text, 'font-size': 12, 'font-weight': 600 }, title));
      const step = narrow ? tickStep * 2 : tickStep;
      for (let t = Math.ceil(lo / step) * step; t <= hi + 1e-9; t += step) {
        s.appendChild(el('line', { x1: X(t), x2: X(t), y1: top - 6, y2: H - bottom + 4, stroke: gridC, 'stroke-width': 1 }));
        s.appendChild(el('text', { x: X(t), y: H - bottom + 18, 'text-anchor': 'middle', fill: C.mute, 'font-size': 11 }, fmt(t)));
      }
      if (band) {
        s.appendChild(el('rect', { x: X(Math.max(lo, band.lo)), y: top - 6, width: Math.max(2, X(Math.min(hi, band.hi)) - X(Math.max(lo, band.lo))), height: H - bottom + 10 - (top - 6), fill: C.c1, 'fill-opacity': 0.14 }));
        s.appendChild(el('line', { x1: X(band.est), x2: X(band.est), y1: top - 6, y2: H - bottom + 4, stroke: C.c1, 'stroke-width': 2 }));
        s.appendChild(el('text', { x: Math.min(X(band.est) + 5, W - 120), y: top - 12, fill: C.text, 'font-size': 11 }, 'Your estimate ' + band.est.toFixed(1) + '%'));
      }
      if (zero) s.appendChild(el('line', { x1: X(0), x2: X(0), y1: top - 6, y2: H - bottom + 4, stroke: C.text, 'stroke-opacity': 0.6, 'stroke-width': 1.5 }));
      s.appendChild(el('text', { x: (left + W - right) / 2, y: H - 4, 'text-anchor': 'middle', fill: C.mute, 'font-size': 11 }, xlabel));
      rows.forEach((x, i) => {
        const y = top + i * rowH + rowH / 2;
        s.appendChild(el('text', { x: left - 10, y: y + 4, 'text-anchor': 'end', fill: C.text, 'font-size': narrow ? 11 : 12 }, name(x)));
        if (x.lo != null) {
          s.appendChild(el('line', { x1: X(Math.max(lo, x.lo)), x2: X(Math.min(hi, x.hi)), y1: y, y2: y, stroke: '#aab2bd', 'stroke-width': 2, 'stroke-linecap': 'round' }));
          for (const e of [x.lo, x.hi]) if (e >= lo && e <= hi) s.appendChild(el('line', { x1: X(e), x2: X(e), y1: y - 5, y2: y + 5, stroke: '#aab2bd', 'stroke-width': 2 }));
        }
        s.appendChild(el('circle', { cx: X(x.value), cy: y, r: 5, fill: '#aab2bd', stroke: C.surface, 'stroke-width': 2 }));
        const edge = x.hi != null ? Math.min(hi, x.hi) : x.value;
        s.appendChild(el('text', { x: X(edge) + 10, y: y + 4, fill: C.text, 'font-size': 12 }, (x.value > 0 ? '+' : '') + x.value.toFixed(x.value % 1 ? 1 : 0) + '%'));
        const hit = el('rect', { x: 0, y: top + i * rowH, width: W, height: rowH, fill: 'transparent' });
        hover(hit, () => x.short + ' (' + x.year + ')', () => [{ color: '#aab2bd', value: (x.value > 0 ? '+' : '') + x.value + '%', label: x.measure }, { value: x.n, label: x.setting }, { value: x.lo == null ? 'not given' : x.lo.toFixed(1) + '% to ' + x.hi.toFixed(1) + '%', label: x.ci_derived ? '95% range (derived by us)' : '95% range' }]);
        s.appendChild(hit);
      });
      return s;
    };
    const fmtp = v => (v > 0 ? '+' : '') + v + '%';
    plot.appendChild(panel('More output (tasks, pull requests, issues per hour). Higher is better.', out, Math.min(0, Math.floor(Math.min(cmp.your_low, ...out.map(x => x.lo == null ? x.value : x.lo)) / 10) * 10), Math.ceil(Math.max(...out.map(x => x.hi == null ? x.value : x.hi), cmp.your_high) / 10) * 10 + 5, 10, fmtp, '% change in output', true, { est: cmp.your_effect, lo: cmp.your_low, hi: cmp.your_high }));
    plot.appendChild(panel('Time to finish a task. Left is faster.', tim, -100, 30, 25, fmtp, '% change in time on the task', true, null));
  }

  const REG = [['c-forest', forest], ['c-split', split], ['c-index', index], ['c-trade', tradeoff], ['c-evidence', evidence]];
  let last = null, timer = null;
  window.renderCharts = function (r) {
    if (r) last = r; if (!last) return;
    for (const [id, fn] of REG) { const h = document.getElementById(id); if (h && h.offsetParent !== null) { try { fn(h, last); } catch (e) { h.textContent = 'Chart unavailable: ' + e.message; } } }
  };
  window.addEventListener('resize', () => { clearTimeout(timer); timer = setTimeout(() => window.renderCharts(), 150); });
})();

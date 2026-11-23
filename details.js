/* =====================================================================
   Vues détaillées : un panneau plein écran par tuile, avec graphiques
   interactifs, chiffres clés, lecture de la situation et explications.
   Utilise les utilitaires et l'état « S » définis dans index.html.
   ===================================================================== */
"use strict";
(() => {
  const DAY = 864e5;
  const last = a => a[a.length - 1];
  const h = (tag, cls, html) => { const n = document.createElement(tag); if (cls) n.className = cls; if (html !== undefined) n.innerHTML = html; return n; };
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const chg = (a, b) => (a / b - 1) * 100;
  const toPts = (k, i = 4) => k.map(x => ({ t: +x[0], v: +x[i] }));
  const sinceDays = (pts, d) => { const t = last(pts).t - d * DAY; return pts.filter(p => p.t >= t); };
  const atDaysAgo = (pts, d) => { const t = last(pts).t - d * DAY; let r = pts[0]; for (const p of pts) { if (p.t <= t) r = p; else break; } return r; };
  const rollMA = (pts, n) => { let s = 0; return pts.map((p, i) => { s += p.v; if (i >= n) s -= pts[i - n].v; return { t: p.t, v: i >= n - 1 ? s / n : NaN }; }); };
  const fin = p => Number.isFinite(p.v);
  const signCls = v => v > 0 ? "up" : v < 0 ? "down" : "";
  const pctH = (v, d = 1) => `<span class="${signCls(v)}">${pct(v, d)}</span>`;
  const dateFR = (t, o = { day: "numeric", month: "short", year: "numeric" }) => new Date(t).toLocaleDateString("fr-FR", o);
  const TONE = { up: "var(--up)", down: "var(--down)", warn: "var(--warn)", neutral: "var(--muted)", info: "var(--macro)" };

  const CACHE = {};
  const cached = (k, ttl, fn) => {
    const c = CACHE[k];
    if (c && Date.now() - c.t < ttl) return c.p;
    const p = fn();
    CACHE[k] = { t: Date.now(), p };
    p.catch(() => { delete CACHE[k]; });
    return p;
  };

  /* ---------------- Données supplémentaires ---------------- */
  const CCY = { EUR: .576, JPY: .136, GBP: .119, CAD: .091, SEK: .042, CHF: .036 };
  const dxyLong = () => cached("dxyLong", 30 * 60e3, async () => {
    const start = new Date(Date.now() - 1100 * DAY).toISOString().slice(0, 10);
    const j = await getJSON([
      `https://api.frankfurter.dev/v1/${start}..?base=USD&symbols=EUR,JPY,GBP,CAD,SEK,CHF`,
      `https://api.frankfurter.app/${start}..?from=USD&to=EUR,JPY,GBP,CAD,SEK,CHF`,
    ], { timeout: 25000 });
    return Object.keys(j.rates).sort().map(d => {
      const r = j.rates[d];
      return { t: Date.parse(d + "T00:00:00Z"), d, r, v: 50.14348112 * Object.entries(CCY).reduce((m, [c, w]) => m * r[c] ** w, 1) };
    });
  });
  const fngYear = () => cached("fngYear", 30 * 60e3, async () => {
    const j = await getJSON("https://api.alternative.me/fng/?limit=400");
    return { raw: j.data, pts: j.data.map(d => ({ t: +d.timestamp * 1000, v: +d.value, c: d.value_classification })).reverse() };
  });
  const btcDaily = async () => { if (!S.btcD) await loadBTC(); return S.btcD; };
  const gecko = async () => { if (!S.global || !S.markets) await loadGecko(); return { g: S.global, m: S.markets }; };
  const stablesAll = async () => { if (!S.stables) await loadStables(); return S.stables; };
  const stableTotal = x => Object.values(x.totalCirculatingUSD || {}).reduce((s, v) => s + v, 0);

  /* ---------------- Graphique détaillé ---------------- */
  function niceTicks(lo, hi, n = 4) {
    const span = hi - lo; if (!(span > 0)) return [lo];
    const raw = span / n, mag = 10 ** Math.floor(Math.log10(raw));
    const step = [1, 2, 2.5, 5, 10].map(k => k * mag).find(s => s >= raw);
    const out = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) out.push(+v.toPrecision(12));
    return out;
  }
  function logTicks(lo, hi) {
    const out = [];
    for (let e = Math.floor(Math.log10(lo)); e <= Math.ceil(Math.log10(hi)); e++)
      for (const k of [1, 2, 5]) { const v = k * 10 ** e; if (v >= lo && v <= hi) out.push(v); }
    return out.length >= 2 ? out : niceTicks(lo, hi);
  }
  const xFmt = span => span <= 2.5 * DAY ? t => new Date(t).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })
    : span <= 200 * DAY ? t => dateFR(t, { day: "numeric", month: "short" }) : t => dateFR(t, { month: "short", year: "2-digit" });
  const tipFmt = span => span <= 10 * DAY ? t => new Date(t).toLocaleString("fr-FR", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : t => dateFR(t);
  const nearest = (pts, t) => { let lo = 0, hi = pts.length - 1; while (hi - lo > 1) { const m = (lo + hi) >> 1; pts[m].t < t ? lo = m : hi = m; } return Math.abs(pts[lo].t - t) <= Math.abs(pts[hi].t - t) ? pts[lo] : pts[hi]; };

  /**
   * cfg: { series:[{name,color,pts,width,area}], fmt, axisFmt, log, bars, barColors:[pos,neg],
   *        yMin, yMax, refs:[{v,label}], bands:[{from,to,color}], legend: Element }
   */
  function lineChart(box, cfg) {
    box._cfg = cfg; drawChart(box, true);
    if (!box._ro) { box._ro = new ResizeObserver(() => drawChart(box, false)); box._ro.observe(box); }
  }
  function drawChart(box, anim) {
    const c = box._cfg, W = box.clientWidth, H = box.clientHeight;
    if (!c || !W || !H) return;
    const series = c.series.filter(s => s.pts && s.pts.filter(fin).length > 1);
    if (!series.length) { box.innerHTML = '<div class="err">Pas de données</div>'; return; }
    const m = { l: 4, r: 58, t: 10, b: 20 }, pw = W - m.l - m.r, ph = H - m.t - m.b;
    const vals = series.flatMap(s => s.pts.filter(fin).map(p => p.v)).filter(v => !c.log || v > 0);
    let lo = Math.min(...vals), hi = Math.max(...vals);
    (c.refs || []).forEach(r => { lo = Math.min(lo, r.v); hi = Math.max(hi, r.v); });
    if (c.bars || c.zero) { lo = Math.min(lo, 0); hi = Math.max(hi, 0); }
    const f = c.log ? Math.log : v => v;
    let a = f(c.yMin ?? lo), b = f(c.yMax ?? hi);
    const pad = (b - a) * .08 || Math.abs(a) * .05 || 1;
    if (c.yMin === undefined) a -= pad;
    if (c.yMax === undefined) b += pad;
    const t0 = Math.min(...series.map(s => s.pts[0].t)), t1 = Math.max(...series.map(s => last(s.pts).t)), span = t1 - t0 || 1;
    const X = t => m.l + (t - t0) / span * pw;
    const Y = v => m.t + (1 - (f(v) - a) / (b - a)) * ph;
    const fmtV = c.fmt || (v => fmt(v, 2)), axisV = c.axisFmt || fmtV, xf = xFmt(span), tf = tipFmt(span);
    const cl = y => Math.max(m.t, Math.min(m.t + ph, y));
    let g = "";

    (c.bands || []).forEach(bd => {
      const y1 = cl(Y(bd.to)), y2 = cl(Y(bd.from));
      if (y2 > y1) g += `<rect x="${m.l}" y="${y1}" width="${pw}" height="${y2 - y1}" fill="${bd.color}" opacity=".09"/>`;
    });
    const yt = c.log ? logTicks(Math.exp(a), Math.exp(b)) : niceTicks(a, b, c.ticks || 4);
    yt.forEach(v => {
      const y = Y(v); if (y < m.t - 1 || y > m.t + ph + 1) return;
      g += `<line x1="${m.l}" x2="${m.l + pw}" y1="${y}" y2="${y}" stroke="rgba(255,255,255,.05)"/><text class="ax" x="${m.l + pw + 8}" y="${y + 3.5}">${esc(axisV(v))}</text>`;
    });
    for (let i = 0; i <= 4; i++) {
      const t = t0 + span * i / 4, anchor = i === 0 ? "start" : i === 4 ? "end" : "middle";
      g += `<text class="ax" x="${X(t)}" y="${H - 5}" text-anchor="${anchor}">${esc(xf(t))}</text>`;
    }
    (c.refs || []).forEach(r => {
      const y = Y(r.v);
      g += `<line x1="${m.l}" x2="${m.l + pw}" y1="${y}" y2="${y}" stroke="var(--muted)" stroke-dasharray="4 4" opacity=".55"/>`;
      if (r.label) g += `<text class="rl" x="${m.l + 6}" y="${y - 4}">${esc(r.label)}</text>`;
    });
    if (c.bars) {
      const s = series[0], n = s.pts.length, bw = Math.max(1, pw / n * .72), y0 = Y(0);
      g += `<line x1="${m.l}" x2="${m.l + pw}" y1="${y0}" y2="${y0}" stroke="var(--faint)"/>`;
      s.pts.forEach((p, i) => {
        const y = Y(p.v), pos = p.v >= 0;
        g += `<rect class="bx${anim ? " draw" : ""}" style="transform-origin:center ${pos ? "bottom" : "top"};animation-delay:${(i / n * .6).toFixed(2)}s" x="${(X(p.t) - bw / 2).toFixed(1)}" y="${Math.min(y, y0).toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(.5, Math.abs(y - y0)).toFixed(1)}" rx="1" fill="${pos ? c.barColors[0] : c.barColors[1]}"/>`;
      });
    } else {
      series.forEach((s, si) => {
        let d = "", pen = false;
        s.pts.forEach(p => { if (!fin(p) || (c.log && p.v <= 0)) { pen = false; return; } d += (pen ? "L" : "M") + X(p.t).toFixed(1) + " " + Y(p.v).toFixed(1); pen = true; });
        if (si === 0 && s.area !== false) {
          const fp = s.pts.filter(fin), id = "lg" + Math.random().toString(36).slice(2, 8);
          g += `<defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${s.color}" stop-opacity=".25"/><stop offset="1" stop-color="${s.color}" stop-opacity="0"/></linearGradient></defs>`;
          g += `<path class="ar${anim ? " draw" : ""}" d="${d}L${X(last(fp).t)} ${m.t + ph}L${X(fp[0].t)} ${m.t + ph}Z" fill="url(#${id})"/>`;
        }
        g += `<path class="ln${anim ? " draw" : ""}" d="${d}" stroke="${s.color}" stroke-width="${s.width || 2}" pathLength="1" style="animation-delay:${si * .15}s"/>`;
      });
    }
    // Étiquette de la dernière valeur (série principale)
    const s0 = series[0], lp = last(s0.pts.filter(fin));
    const ly = Y(lp.v), lbl = esc(fmtV(lp.v)), lw = Math.max(44, lbl.length * 6.4 + 10);
    g += `<g class="tg${anim ? " draw" : ""}"><rect x="${m.l + pw + 2}" y="${ly - 9}" width="${lw}" height="18" rx="5" fill="var(--bg)" stroke="${s0.color}"/><text x="${m.l + pw + 7}" y="${ly + 3.5}">${lbl}</text></g>`;
    // Couche réticule
    g += `<line class="xh" id="xh" y1="${m.t}" y2="${m.t + ph}" stroke="var(--muted)" stroke-dasharray="3 3"/>`;
    series.forEach((s, i) => { g += `<circle class="xh" data-i="${i}" r="4" fill="${s.color}" stroke="var(--bg)" stroke-width="2"/>`; });
    box.innerHTML = `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">${g}</svg><div class="lc-tip"></div>`;

    if (c.legend) {
      c.legend.innerHTML = series.length > 1 ? series.map(s => { const lv = last(s.pts.filter(fin)); return `<span><i class="sw" style="background:${s.color}"></i>${esc(s.name)}<b>${esc(fmtV(lv.v))}</b></span>`; }).join("") : "";
    }
    const svg = box.querySelector("svg"), line = svg.querySelector("#xh"), dots = svg.querySelectorAll("circle.xh"), tip = box.querySelector(".lc-tip");
    const show = e => {
      const r = box.getBoundingClientRect(), x = Math.max(m.l, Math.min(m.l + pw, e.clientX - r.left));
      const t = t0 + (x - m.l) / pw * span;
      const p0 = nearest(s0.pts, t), px = X(p0.t);
      line.setAttribute("x1", px); line.setAttribute("x2", px);
      let rows = "";
      series.forEach((s, i) => {
        const p = nearest(s.pts, p0.t);
        if (!fin(p)) { dots[i].setAttribute("r", 0); return; }
        dots[i].setAttribute("r", 4); dots[i].setAttribute("cx", X(p.t)); dots[i].setAttribute("cy", Y(p.v));
        rows += `<div><i class="sw" style="background:${s.color}"></i>${series.length > 1 ? esc(s.name) + " " : ""}<b>${esc(fmtV(p.v))}</b>${p.note ? ` <span class="muted">${esc(p.note)}</span>` : ""}</div>`;
      });
      tip.innerHTML = `<div class="d">${esc(tf(p0.t))}</div>${rows}`;
      const tw = tip.offsetWidth;
      tip.style.left = (px + 12 + tw > W ? px - 12 - tw : px + 12) + "px";
      box.classList.add("hover");
    };
    box.onpointerdown = box.onpointermove = show;
    box.onpointerleave = box.onpointercancel = () => box.classList.remove("hover");
  }

  /* ---------------- Modale ---------------- */
  let current = null;
  function openDetail(key, tile) {
    const def = DETAILS[key];
    if (!def) return;
    closeDetail(true);
    const back = h("div", "dm-back"), dm = h("div", "dm");
    dm.setAttribute("role", "dialog");
    dm.innerHTML = `<header class="dm-head"><div><div class="dm-kicker">${def.kicker}</div><h2>${def.title}</h2></div><div class="dm-tabs"></div><button class="dm-close" aria-label="Fermer">✕</button></header>
      <div class="dm-body"><div class="dm-main"></div><aside class="dm-side"></aside></div>`;
    document.body.append(back, dm);
    // Animation « zoom depuis la tuile »
    const r0 = tile.getBoundingClientRect(), r1 = dm.getBoundingClientRect();
    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const from = `translate(${r0.left - r1.left}px, ${r0.top - r1.top}px) scale(${r0.width / r1.width}, ${r0.height / r1.height})`;
    if (!reduce) { dm.style.transition = "none"; dm.style.transform = from; dm.style.opacity = ".4"; dm.getBoundingClientRect(); dm.style.transition = ""; }
    requestAnimationFrame(() => { dm.style.transform = ""; dm.style.opacity = ""; dm.classList.add("in"); back.classList.add("in"); });
    current = { dm, back, from, reduce };
    back.onclick = () => closeDetail();
    dm.querySelector(".dm-close").onclick = () => closeDetail();
    const ctx = makeCtx(dm);
    def.render(ctx).catch(e => {
      console.warn(key, e);
      ctx.main.innerHTML = `<div class="dsec grow"><div class="err">Données indisponibles pour le moment.<br>Réessaie dans quelques minutes.</div></div>`;
    });
  }
  function closeDetail(instant) {
    if (!current) return;
    const { dm, back, from, reduce } = current;
    current = null;
    if (instant || reduce) { dm.remove(); back.remove(); return; }
    dm.classList.remove("in"); back.classList.remove("in");
    dm.style.transform = from; dm.style.opacity = "0";
    setTimeout(() => { dm.remove(); back.remove(); }, 450);
  }
  document.addEventListener("keydown", e => { if (e.key === "Escape") closeDetail(); });

  function makeCtx(dm) {
    const main = dm.querySelector(".dm-main"), side = dm.querySelector(".dm-side"), tabsEl = dm.querySelector(".dm-tabs");
    const ctx = {
      main, side,
      /** Onglets de période dans l'en-tête. */
      tabs(opts, active, onChange) {
        tabsEl.innerHTML = "";
        opts.forEach(([id, label]) => {
          const b = h("button", "", label);
          b.setAttribute("aria-pressed", String(id === active));
          b.onclick = () => { if (b.getAttribute("aria-pressed") === "true") return; tabsEl.querySelectorAll("button").forEach(x => x.setAttribute("aria-pressed", "false")); b.setAttribute("aria-pressed", "true"); onChange(id); };
          tabsEl.appendChild(b);
        });
        onChange(active);
      },
      /** Section graphique ; renvoie { box, legend, title }. */
      chart(parent, title, note) {
        const sec = h("section", "dsec grow");
        sec.innerHTML = `<div class="dsec-h"><span class="tt">${title}</span><span class="lc-legend"></span>${note ? `<small>${note}</small>` : ""}</div><div class="lc"></div>`;
        parent.appendChild(sec);
        return { sec, box: sec.querySelector(".lc"), legend: sec.querySelector(".lc-legend"), title: sec.querySelector(".tt") };
      },
      section(parent, title, html, cls = "") {
        const sec = h("section", "dsec " + cls, `<div class="dsec-h"><span>${title}</span></div>`);
        const body = h("div", "", html || ""); sec.appendChild(body); parent.appendChild(sec);
        return body;
      },
      reading(label, tone, paragraphs) {
        const sec = h("section", "dsec read");
        sec.style.setProperty("--tone", TONE[tone] || tone);
        sec.innerHTML = `<div class="dsec-h"><span>Lecture actuelle</span></div><span class="pill">${label}</span>${paragraphs.map(p => `<p>${p}</p>`).join("")}`;
        side.appendChild(sec);
      },
      kv(title, rows, parent = side) {
        return ctx.section(parent, title, `<div class="dkv">${rows.filter(Boolean).map(([k, v]) => `<span>${k}</span><b>${v}</b>`).join("")}</div>`);
      },
      levels(title, rows, parent = side) {
        return ctx.section(parent, title, `<div class="lvl">${rows.map(([r, t, c, on]) => `<span class="r" style="--c:${TONE[c] || c}">${r}</span><span class="t${on ? " on" : ""}" style="--c:${TONE[c] || c}">${t}</span>`).join("")}</div>`);
      },
      text(title, paragraphs, parent = side) {
        return ctx.section(parent, title, `<div class="dtext">${paragraphs.map(p => `<p>${p}</p>`).join("")}</div>`);
      },
    };
    return ctx;
  }

  /* ---------------- Fonctions de calcul ---------------- */
  function rsiSeries(pts, n = 14) {
    const out = pts.map(p => ({ t: p.t, v: NaN }));
    let g = 0, l = 0;
    for (let i = 1; i < pts.length; i++) {
      const d = pts[i].v - pts[i - 1].v, up = Math.max(d, 0), dn = Math.max(-d, 0);
      if (i <= n) { g += up / n; l += dn / n; if (i < n) continue; }
      else { g = (g * (n - 1) + up) / n; l = (l * (n - 1) + dn) / n; }
      out[i].v = l === 0 ? 100 : 100 - 100 / (1 + g / l);
    }
    return out;
  }
  function corr(x, y) {
    const n = x.length; if (n < 5) return NaN;
    const mx = x.reduce((s, v) => s + v, 0) / n, my = y.reduce((s, v) => s + v, 0) / n;
    let sxy = 0, sxx = 0, syy = 0;
    for (let i = 0; i < n; i++) { sxy += (x[i] - mx) * (y[i] - my); sxx += (x[i] - mx) ** 2; syy += (y[i] - my) ** 2; }
    return sxy / Math.sqrt(sxx * syy);
  }
  /** Rendements journaliers BTC et DXY alignés sur les jours de cotation BCE. */
  function alignedReturns(dxy, btcK) {
    const btc = new Map(btcK.map(k => [new Date(+k[0]).toISOString().slice(0, 10), +k[4]]));
    const out = [];
    for (let i = 1; i < dxy.length; i++) {
      const p0 = btc.get(dxy[i - 1].d), p1 = btc.get(dxy[i].d);
      if (p0 && p1) out.push({ t: dxy[i].t, b: p1 / p0 - 1, d: dxy[i].v / dxy[i - 1].v - 1 });
    }
    return out;
  }
  function vol30(closes) {
    const r = []; for (let i = closes.length - 30; i < closes.length; i++) r.push(Math.log(closes[i] / closes[i - 1]));
    const m = r.reduce((s, v) => s + v, 0) / r.length;
    return Math.sqrt(r.reduce((s, v) => s + (v - m) ** 2, 0) / (r.length - 1)) * Math.sqrt(365) * 100;
  }
  const countdown = ms => { if (ms <= 0) return "maintenant"; const m = Math.floor(ms / 60000); const d = Math.floor(m / 1440), hh = Math.floor(m % 1440 / 60), mm = m % 60; return (d ? d + " j " : "") + (d || hh ? hh + " h " : "") + mm + " min"; };

  /* =====================================================================
     DÉTAILS PAR TUILE
     ===================================================================== */
  const DETAILS = {};

  /* ---------- Bitcoin ---------- */
  DETAILS.btc = {
    kicker: "Bitcoin · BTC/USDT", title: "Prix, tendance et volatilité",
    async render(x) {
      const D = await btcDaily(), W = S.btcW, dp = toPts(D), closes = dp.map(p => p.v);
      const ma50 = rollMA(dp, 50), ma200 = rollMA(dp, 200), wp = toPts(W), wma = rollMA(wp, 200);
      const c = x.chart(x.main, "Prix BTC");
      const RANGES = {
        "24h": async () => [{ name: "BTC", color: "var(--btc)", pts: toPts(await cached("btc15m", 120e3, () => klines("BTCUSDT", "15m", 96))) }],
        "7j": async () => [{ name: "BTC", color: "var(--btc)", pts: toPts(S.btcH) }],
        "3m": async () => [{ name: "BTC", color: "var(--btc)", pts: dp.slice(-90) }, { name: "MM50", color: "var(--macro)", pts: ma50.slice(-90), width: 1.6 }, { name: "MM200", color: "var(--eth)", pts: ma200.slice(-90), width: 1.6 }],
        "1a": async () => [{ name: "BTC", color: "var(--btc)", pts: dp.slice(-365) }, { name: "MM50", color: "var(--macro)", pts: ma50.slice(-365), width: 1.6 }, { name: "MM200", color: "var(--eth)", pts: ma200.slice(-365), width: 1.6 }],
        "max": async () => [{ name: "BTC (hebdo)", color: "var(--btc)", pts: wp }, { name: "MM 200 sem.", color: "var(--eth)", pts: wma, width: 1.6 }],
      };
      const TITLES = { "24h": "Prix BTC · 24 h (15 min)", "7j": "Prix BTC · 7 jours (horaire)", "3m": "Prix BTC · 3 mois", "1a": "Prix BTC · 1 an", "max": "Prix BTC · historique hebdo (échelle log)" };
      x.tabs([["24h", "24 h"], ["7j", "7 j"], ["3m", "3 mois"], ["1a", "1 an"], ["max", "Max"]], "3m", async id => {
        c.title.textContent = TITLES[id];
        lineChart(c.box, { series: await RANGES[id](), fmt: usd, axisFmt: v => v >= 1000 ? fmt(v / 1000, v >= 1e4 ? 0 : 1) + " k" : fmt(v, 0), log: id === "max", legend: c.legend });
      });

      const tk = S.tick && S.tick.BTCUSDT, price = tk ? tk.last : last(closes);
      const m50 = last(ma50).v, m200 = last(ma200).v;
      // Dernier croisement MM50 / MM200
      let crossIdx = -1;
      for (let i = dp.length - 1; i > 200; i--) { if (Math.sign(ma50[i].v - ma200[i].v) !== Math.sign(ma50[i - 1].v - ma200[i - 1].v)) { crossIdx = i; break; } }
      const golden = m50 > m200;
      const crossTxt = crossIdx > 0 ? `${golden ? "Golden cross" : "Death cross"} (MM50 ${golden ? "au-dessus" : "sous"} la MM200) depuis le <b>${dateFR(dp[crossIdx].t)}</b>, soit ${Math.round((Date.now() - dp[crossIdx].t) / DAY)} jours.` : "";
      const [lbl, tone, txt] = price > m50 && price > m200 ? ["TENDANCE HAUSSIÈRE", "up", "Le prix est au-dessus de ses moyennes 50 et 200 jours : la structure de marché est haussière."]
        : price < m50 && price < m200 ? ["TENDANCE BAISSIÈRE", "down", "Le prix est sous ses moyennes 50 et 200 jours : les vendeurs contrôlent la tendance de fond."]
        : price > m200 ? ["CORRECTION DANS UN MARCHÉ HAUSSIER", "warn", "Le prix a cassé sa MM50 mais reste au-dessus de la MM200 : correction tant que la MM200 tient."]
        : ["REBOND SOUS LA MM200", "warn", "Le prix repasse au-dessus de la MM50 mais reste sous la MM200 : reprise à confirmer."];
      x.reading(lbl, tone, [txt, crossTxt].filter(Boolean));

      const highs = D.map(k => ({ t: +k[0], v: +k[2] })).concat(W.map(k => ({ t: +k[0], v: +k[2] })));
      const ath = highs.reduce((a, b) => b.v > a.v ? b : a);
      const y1 = dp.slice(-365), hi52 = Math.max(...y1.map(p => p.v)), lo52 = Math.min(...y1.map(p => p.v));
      const vol = vol30(closes);
      x.kv("Chiffres clés", [
        ["Prix", usd(price)],
        tk && ["Variation 24 h", pctH(tk.chg, 2)],
        ["7 jours", pctH(chg(price, atDaysAgo(dp, 7).v))],
        ["30 jours", pctH(chg(price, atDaysAgo(dp, 30).v))],
        ["90 jours", pctH(chg(price, atDaysAgo(dp, 90).v))],
        ["1 an", pctH(chg(price, atDaysAgo(dp, 365).v))],
        tk && ["Bas / haut 24 h", `${usd(tk.low)} · ${usd(tk.high)}`],
        tk && tk.vol && ["Volume 24 h (Binance)", money(tk.vol)],
        ["Plus haut historique", `${usd(ath.v)} <span class="muted">· ${dateFR(ath.t, { month: "short", year: "numeric" })}</span>`],
        ["Distance au sommet", pctH(chg(price, ath.v))],
        ["Plus haut / bas 52 sem.", `${usd(hi52)} · ${usd(lo52)}`],
        ["MM50 jours", `${usd(m50)} <span class="muted">(${pct(chg(price, m50), 1)})</span>`],
        ["MM200 jours", `${usd(m200)} <span class="muted">(${pct(chg(price, m200), 1)})</span>`],
        ["Volatilité 30 j (annualisée)", fmt(vol, 0) + " %"],
      ]);
      x.levels("Volatilité : comment la lire", [
        ["< 35 %", "Compression : un gros mouvement se prépare souvent", "info", vol < 35],
        ["35 – 60 %", "Régime normal pour Bitcoin", "neutral", vol >= 35 && vol <= 60],
        ["> 60 %", "Marché agité : capitulation ou emballement", "warn", vol > 60],
      ]);
      x.text("Comment le lire", [
        "<b>MM200 jours</b> : la frontière la plus suivie entre marché haussier et baissier. Les grands marchés haussiers de BTC se sont déroulés au-dessus.",
        "<b>MM50 jours</b> : la tendance de moyen terme. Un passage sous la MM50 dans un marché haussier est souvent une simple correction.",
        "<b>Golden / death cross</b> : croisement des MM50 et MM200. Signal lent, qui confirme une tendance plus qu'il ne l'anticipe.",
      ]);
    },
  };

  /* ---------- DXY ---------- */
  DETAILS.dxy = {
    kicker: "Dollar Index · recalculé (taux BCE)", title: "Le dollar, ses composantes et son lien avec BTC",
    async render(x) {
      const [pts, D] = await Promise.all([dxyLong(), btcDaily()]);
      const ma50 = rollMA(pts, 50), ma200 = rollMA(pts, 200);
      const ret = alignedReturns(pts, D);
      const rc = ret.map((r, i) => i < 29 ? null : { t: r.t, v: corr(ret.slice(i - 29, i + 1).map(q => q.b), ret.slice(i - 29, i + 1).map(q => q.d)) }).filter(Boolean);
      const c1 = x.chart(x.main, "DXY");
      const c2 = x.chart(x.main, "Corrélation glissante 30 j · BTC / DXY", "−1 = parfaitement inverse");
      const DAYS = { "3m": 92, "6m": 183, "1a": 365, "2a": 730 };
      x.tabs([["3m", "3 mois"], ["6m", "6 mois"], ["1a", "1 an"], ["2a", "2 ans"]], "1a", id => {
        const d = DAYS[id];
        lineChart(c1.box, { series: [{ name: "DXY", color: "var(--macro)", pts: sinceDays(pts, d) }, { name: "MM50", color: "var(--btc)", pts: sinceDays(ma50, d), width: 1.6 }, { name: "MM200", color: "var(--eth)", pts: sinceDays(ma200, d), width: 1.6 }], fmt: v => fmt(v, 2), legend: c1.legend });
        lineChart(c2.box, { series: [{ name: "Corrélation", color: "var(--stable)", pts: sinceDays(rc, d) }], fmt: v => fmt(v, 2), yMin: -1, yMax: 1, refs: [{ v: 0 }], bands: [{ from: -1, to: -.3, color: "var(--macro)" }, { from: .3, to: 1, color: "var(--warn)" }] });
      });

      const v = last(pts).v, m50 = last(ma50).v, m200 = last(ma200).v, v1m = atDaysAgo(pts, 30).v;
      const up1m = v > v1m;
      const [lbl, tone] = v < m50 && v < m200 ? ["DOLLAR FAIBLE", "up"] : v > m50 && v > m200 ? ["DOLLAR FORT", "down"] : ["DOLLAR SANS DIRECTION", "warn"];
      x.reading(lbl, tone, [
        `Le DXY est à <b>${fmt(v, 2)}</b>, ${v < m50 ? "sous" : "au-dessus de"} sa MM50 (${pct(chg(v, m50), 2)}) et ${v < m200 ? "sous" : "au-dessus de"} sa MM200 (${pct(chg(v, m200), 2)}).`,
        `Sur 1 mois il ${up1m ? "monte" : "baisse"} de ${pct(Math.abs(chg(v, v1m)), 2).replace("+", "")} : ${up1m ? "un dollar qui se renforce resserre la liquidité mondiale, c'est un <b>vent contraire</b> pour la crypto." : "un dollar qui se replie libère de la liquidité, un contexte <b>porteur</b> pour la crypto."}`,
      ]);
      const y1 = sinceDays(pts, 365).map(p => p.v);
      const c30 = last(rc) ? last(rc).v : NaN, c90 = corr(ret.slice(-90).map(q => q.b), ret.slice(-90).map(q => q.d));
      x.kv("Chiffres clés", [
        ["DXY (clôture BCE)", `${fmt(v, 2)} <span class="muted">· ${dateFR(last(pts).t, { day: "numeric", month: "short" })}</span>`],
        ["1 jour", pctH(chg(v, pts[pts.length - 2].v), 2)],
        ["1 semaine", pctH(chg(v, atDaysAgo(pts, 7).v), 2)],
        ["1 mois", pctH(chg(v, v1m), 2)],
        ["3 mois", pctH(chg(v, atDaysAgo(pts, 91).v), 2)],
        ["1 an", pctH(chg(v, atDaysAgo(pts, 365).v), 2)],
        ["MM50 / MM200", `${fmt(m50, 2)} · ${fmt(m200, 2)}`],
        ["Plus haut / bas 52 sem.", `${fmt(Math.max(...y1), 2)} · ${fmt(Math.min(...y1), 2)}`],
        ["Corrélation BTC 30 j", fmt(c30, 2)],
        ["Corrélation BTC 90 j", fmt(c90, 2)],
      ]);
      // Composantes du DXY et leur contribution sur 1 mois
      const r0 = last(pts).r, r1 = atDaysAgo(pts, 30).r;
      const rows = Object.entries(CCY).map(([cc, w]) => {
        const inv = cc === "EUR" || cc === "GBP";
        const pair = inv ? `${cc}/USD` : `USD/${cc}`, now = inv ? 1 / r0[cc] : r0[cc], then = inv ? 1 / r1[cc] : r1[cc];
        return { cc, w, pair, now, ch: chg(now, then), contrib: w * Math.log(r0[cc] / r1[cc]) * 100 };
      });
      const mx = Math.max(...rows.map(r => Math.abs(r.contrib)), .01);
      x.section(x.side, "Composantes · effet sur le DXY en 1 mois", `<div class="tbl">
        <div class="th" style="grid-template-columns:1fr 42px 70px 64px 60px"><span>Paire</span><span class="n">Poids</span><span class="n">Cours</span><span class="n">1 mois</span><span class="n">Effet</span></div>
        ${rows.map((r, i) => `<div style="grid-template-columns:1fr 42px 70px 64px 60px;animation-delay:${.3 + i * .06}s"><span>${r.pair}</span><span class="n s">${fmt(r.w * 100, 1)} %</span><span class="n">${fmt(r.now, r.now > 20 ? 2 : 4)}</span><span class="n ${signCls(r.ch)}">${pct(r.ch, 1)}</span>
          <span class="hb mid" title="${pct(r.contrib, 2)}"><i style="left:${r.contrib < 0 ? 50 - Math.abs(r.contrib) / mx * 50 : 50}%;width:${Math.abs(r.contrib) / mx * 50}%;background:${r.contrib > 0 ? "var(--down)" : "var(--up)"}"></i></span></div>`).join("")}
        </div><div class="sub" style="margin-top:6px">Barre rouge = pousse le dollar à la hausse (défavorable crypto), verte = le tire vers le bas.</div>`);
      x.levels("Repères", [
        ["< 100", "Dollar faible : historiquement porteur pour BTC", "up", v < 100],
        ["100 – 105", "Zone neutre", "neutral", v >= 100 && v <= 105],
        ["105 – 110", "Dollar fort : liquidité sous pression", "warn", v > 105 && v <= 110],
        ["> 110", "Dollar très fort : stress sur les actifs risqués", "down", v > 110],
      ]);
      x.text("Comment le lire", [
        "Le <b>DXY</b> mesure le dollar face à 6 devises, l'euro pesant 57,6 %. Il est ici recalculé avec la formule officielle à partir des taux de référence de la BCE, publiés une fois par jour.",
        "Un dollar fort renchérit le crédit mondial et assèche la liquidité : les actifs risqués comme la crypto en souffrent. Les grandes hausses de BTC ont souvent coïncidé avec un DXY en baisse.",
        "La <b>corrélation</b> n'est pas constante : quand elle est proche de 0, BTC suit d'autres facteurs (ETF, flux propres à la crypto).",
      ]);
    },
  };

  /* ---------- Régime ---------- */
  DETAILS.regime = {
    kicker: "Score composite 0 – 100", title: "Régime de marché : d'où vient le score",
    async render(x) {
      const [D, dxy, fng, st] = await Promise.all([btcDaily(), dxyLong().catch(() => null), fngYear().catch(() => null), stablesAll().catch(() => null)]);
      const dp = toPts(D), ma200 = rollMA(dp, 200);
      const dKey = t => new Date(t).toISOString().slice(0, 10);
      const dxyMA = dxy ? rollMA(dxy, 50) : null;
      const fngMap = fng ? new Map(fng.pts.map(p => [dKey(p.t), p.v])) : null;
      const stPts = st ? st.map(x => ({ t: +x.date * 1000, v: stableTotal(x) })) : null;
      const stMap = stPts ? new Map(stPts.map(p => [dKey(p.t), p.v])) : null;
      const factorsAt = i => {
        const t = dp[i].t, f = {};
        if (Number.isFinite(ma200[i].v)) { const dev = chg(dp[i].v, ma200[i].v); f.trend = { v: clamp(dev / 25), raw: dev }; }
        if (dxy) { let j = -1; for (let k = dxy.length - 1; k >= 0; k--) if (dxy[k].t <= t) { j = k; break; } if (j >= 49) { const dev = chg(dxy[j].v, dxyMA[j].v); f.dollar = { v: clamp(-dev / 2), raw: dev }; } }
        if (fngMap && fngMap.has(dKey(t))) { const v = fngMap.get(dKey(t)); f.sentiment = { v: (v - 50) / 50, raw: v }; }
        if (stMap) { const a = stMap.get(dKey(t)), b = stMap.get(dKey(t - 30 * DAY)); if (a && b) { const c = chg(a, b); f.liquidity = { v: clamp(c / 3), raw: c }; } }
        const vals = Object.values(f);
        return { f, score: vals.length ? 50 + 50 * vals.reduce((s, q) => s + q.v, 0) / vals.length : NaN };
      };
      const hist = [];
      for (let i = Math.max(200, dp.length - 365); i < dp.length; i++) { const r = factorsAt(i); hist.push({ t: dp[i].t, v: Math.round(r.score) }); }
      const BANDS = [{ from: 0, to: 25, color: "#ef4444" }, { from: 25, to: 42, color: "#f97316" }, { from: 42, to: 58, color: "#eab308" }, { from: 58, to: 75, color: "#84cc16" }, { from: 75, to: 100, color: "#22c55e" }];
      const c1 = x.chart(x.main, "Historique du score (reconstitué)");
      const c2 = x.chart(x.main, "Bitcoin sur la même période");
      const DAYS = { "3m": 92, "6m": 183, "1a": 365 };
      x.tabs([["3m", "3 mois"], ["6m", "6 mois"], ["1a", "1 an"]], "6m", id => {
        lineChart(c1.box, { series: [{ name: "Score", color: "var(--text)", pts: sinceDays(hist, DAYS[id]), area: false }], fmt: v => fmt(v, 0), yMin: 0, yMax: 100, bands: BANDS });
        lineChart(c2.box, { series: [{ name: "BTC", color: "var(--btc)", pts: sinceDays(dp, DAYS[id]) }], fmt: usd, axisFmt: v => fmt(v / 1000, 0) + " k" });
      });

      // Score actuel : mêmes facteurs que sur la tuile (données les plus récentes)
      const F = S.factors, order = [["dollar", "Dollar (DXY vs MM50)", "−2 % → +1 · +2 % → −1"], ["trend", "Tendance BTC (vs MM200)", "+25 % → +1 · −25 % → −1"], ["sentiment", "Sentiment (Fear & Greed)", "100 → +1 · 0 → −1"], ["liquidity", "Liquidité (stablecoins 30 j)", "+3 % → +1 · −3 % → −1"]];
      const live = order.filter(([k]) => F[k]);
      const score = live.length ? Math.round(50 + 50 * live.reduce((s, [k]) => s + F[k].v, 0) / live.length) : last(hist).v;
      const lab = score < 25 ? ["RISK-OFF", "down"] : score < 42 ? ["PRUDENT", "warn"] : score < 58 ? ["NEUTRE", "neutral"] : score < 75 ? ["FAVORABLE", "up"] : ["RISK-ON", "up"];
      const best = live.slice().sort((a, b) => F[b[0]].v - F[a[0]].v);
      x.reading(`${lab[0]} · ${score}/100`, lab[1], [
        live.length ? `Principal soutien : <b>${best[0][1].split(" (")[0]}</b> (${F[best[0][0]].txt}). Principal frein : <b>${last(best)[1].split(" (")[0]}</b> (${F[last(best)[0]].txt}).` : "Données en cours de chargement.",
        `Il y a 30 jours, le score reconstitué était de <b>${atDaysAgo(hist, 30).v}</b>.`,
      ]);
      x.section(x.side, "Décomposition du score actuel", `<div class="tbl">
        <div class="th" style="grid-template-columns:1fr 84px 54px"><span>Facteur</span><span class="n">Mesure</span><span class="n">Points</span></div>
        ${order.map(([k, name, rule], i) => { const q = F[k]; if (!q) return `<div style="grid-template-columns:1fr 84px 54px"><span>${name}</span><span class="n s">—</span><span class="n s">—</span></div>`;
          const pts = q.v * 50 / live.length;
          return `<div style="grid-template-columns:1fr 84px 54px;animation-delay:${.3 + i * .07}s"><span>${name}<br><span class="s" style="font-size:11px">${rule}</span></span><span class="n">${q.txt.replace(/ \/ MM\d+|Stables |F&G /g, "")}</span><span class="n ${signCls(pts)}">${pts > 0 ? "+" : ""}${fmt(pts, 1)}</span></div>
          <div style="grid-template-columns:1fr;padding-top:0;border:0;animation-delay:${.3 + i * .07}s"><span class="hb mid"><i style="left:${q.v < 0 ? 50 + q.v * 50 : 50}%;width:${Math.abs(q.v) * 50}%;background:${q.v >= 0 ? "var(--up)" : "var(--down)"}"></i></span></div>`; }).join("")}
        </div><div class="sub" style="margin-top:6px">Score = 50 + 50 × moyenne des facteurs (chacun entre −1 et +1).</div>`);
      x.levels("Échelle", [
        ["0 – 25", "Risk-off : conditions hostiles", "down", score < 25],
        ["25 – 42", "Prudent", "#f97316", score >= 25 && score < 42],
        ["42 – 58", "Neutre", "#eab308", score >= 42 && score < 58],
        ["58 – 75", "Favorable", "#84cc16", score >= 58 && score < 75],
        ["75 – 100", "Risk-on : tous les voyants au vert", "up", score >= 75],
      ]);
      x.text("Méthode", [
        "Le score combine 4 familles d'indicateurs reconnues : la <b>liquidité en dollars</b> (DXY), la <b>tendance de fond</b> de BTC (MM200), le <b>sentiment</b> (Fear & Greed) et la <b>liquidité crypto</b> (offre de stablecoins).",
        "L'historique est reconstitué jour par jour avec les mêmes règles. C'est un outil de contexte, pas un signal d'achat ou de vente : un sentiment très bas peut être une opportunité à contre-courant.",
      ]);
    },
  };

  /* ---------- Fear & Greed ---------- */
  DETAILS.fng = {
    kicker: "Crypto Fear & Greed Index · alternative.me", title: "Sentiment du marché",
    async render(x) {
      const [{ raw, pts }, D] = await Promise.all([fngYear(), btcDaily()]);
      const dp = toPts(D);
      const BANDS = [{ from: 0, to: 25, color: "#ef4444" }, { from: 75, to: 100, color: "#22c55e" }];
      const c1 = x.chart(x.main, "Fear & Greed", "rouge = peur extrême · vert = avidité extrême");
      const c2 = x.chart(x.main, "Bitcoin sur la même période");
      const DAYS = { "30j": 30, "90j": 90, "1a": 365 };
      const FR = { "Extreme Fear": "peur extrême", "Fear": "peur", "Neutral": "neutre", "Greed": "avidité", "Extreme Greed": "avidité extrême" };
      x.tabs([["30j", "30 j"], ["90j", "90 j"], ["1a", "1 an"]], "90j", id => {
        lineChart(c1.box, { series: [{ name: "F&G", color: "var(--warn)", pts: sinceDays(pts, DAYS[id]).map(p => ({ ...p, note: FR[p.c] })) }], fmt: v => fmt(v, 0), yMin: 0, yMax: 100, bands: BANDS, refs: [{ v: 50 }] });
        lineChart(c2.box, { series: [{ name: "BTC", color: "var(--btc)", pts: sinceDays(dp, DAYS[id]) }], fmt: usd, axisFmt: v => fmt(v / 1000, 0) + " k" });
      });
      const v = last(pts).v, y1 = pts.slice(-365), d90 = pts.slice(-90);
      const avg = a => a.reduce((s, p) => s + p.v, 0) / a.length;
      const mn = y1.reduce((a, b) => b.v < a.v ? b : a), mxp = y1.reduce((a, b) => b.v > a.v ? b : a);
      const [lbl, tone, txt] = v < 25 ? ["PEUR EXTRÊME", "up", "La foule panique. Historiquement, ces phases ont souvent offert de bons points d'entrée à moyen terme (approche contrariante)."]
        : v < 45 ? ["PEUR", "warn", "Le marché est nerveux, les investisseurs restent prudents."]
        : v < 56 ? ["NEUTRE", "neutral", "Pas d'excès dans un sens ni dans l'autre."]
        : v < 76 ? ["AVIDITÉ", "warn", "L'optimisme domine ; la prudence augmente si l'indice continue de grimper."]
        : ["AVIDITÉ EXTRÊME", "down", "Euphorie : historiquement, ces zones précèdent souvent des corrections. Prudence sur les nouveaux achats."];
      x.reading(`${lbl} · ${v}`, tone, [txt, `Moyenne des 30 derniers jours : <b>${fmt(avg(pts.slice(-30)), 0)}</b>, soit un sentiment ${v > avg(pts.slice(-30)) ? "en amélioration" : "en dégradation"}.`]);
      const upd = raw[0] && raw[0].time_until_update ? countdown(+raw[0].time_until_update * 1000) : null;
      x.kv("Chiffres clés", [
        ["Aujourd'hui", `${v} · ${FR[last(pts).c] || ""}`],
        ["Hier", pts[pts.length - 2].v],
        ["Il y a 7 j / 30 j", `${atDaysAgo(pts, 7).v} · ${atDaysAgo(pts, 30).v}`],
        ["Moyenne 30 j", fmt(avg(pts.slice(-30)), 0)],
        ["Moyenne 1 an", fmt(avg(y1), 0)],
        ["Plus bas 1 an", `${mn.v} <span class="muted">· ${dateFR(mn.t, { day: "numeric", month: "short" })}</span>`],
        ["Plus haut 1 an", `${mxp.v} <span class="muted">· ${dateFR(mxp.t, { day: "numeric", month: "short" })}</span>`],
        ["Jours en peur extrême (90 j)", d90.filter(p => p.v < 25).length],
        ["Jours en avidité extrême (90 j)", d90.filter(p => p.v > 75).length],
        upd && ["Prochaine mise à jour", "dans " + upd],
      ]);
      x.levels("Composition de l'indice", [
        ["25 %", "Volatilité vs moyenne 30 / 90 j", "neutral"],
        ["25 %", "Momentum et volume du marché", "neutral"],
        ["15 %", "Réseaux sociaux (engagement)", "neutral"],
        ["15 %", "Sondages (actuellement suspendus)", "neutral"],
        ["10 %", "Dominance de Bitcoin", "neutral"],
        ["10 %", "Tendances de recherche Google", "neutral"],
      ]);
      x.text("Comment le lire", [
        "L'indice est surtout utile <b>à contre-courant</b> : « soyez craintif quand les autres sont avides, et avide quand les autres sont craintifs ».",
        "Comparez-le au graphique de BTC : les creux de sentiment coïncident souvent avec des creux de prix locaux.",
      ]);
    },
  };

  /* ---------- Dérivés ---------- */
  DETAILS.deriv = {
    kicker: "Binance Futures · BTCUSDT perpétuel", title: "Levier, funding et positionnement",
    async render(x) {
      const q = p => getJSON(FAPI + p);
      const [fr, oiD, oiH, ls, top, tk, prem, D] = await Promise.allSettled([
        q("/fapi/v1/fundingRate?symbol=BTCUSDT&limit=90"),
        q("/futures/data/openInterestHist?symbol=BTCUSDT&period=1d&limit=30"),
        q("/futures/data/openInterestHist?symbol=BTCUSDT&period=1h&limit=25"),
        q("/futures/data/globalLongShortAccountRatio?symbol=BTCUSDT&period=4h&limit=42"),
        q("/futures/data/topLongShortPositionRatio?symbol=BTCUSDT&period=4h&limit=42"),
        q("/futures/data/takerlongshortRatio?symbol=BTCUSDT&period=1h&limit=24"),
        q("/fapi/v1/premiumIndex?symbol=BTCUSDT"),
        btcDaily(),
      ]).then(r => r.map(x => x.status === "fulfilled" ? x.value : null));
      if (!fr && !oiD && !prem) throw new Error("futures indisponibles");
      const c1 = x.chart(x.main, "Funding rate par période de 8 h · 30 j", "orange = les longs paient · bleu = les shorts paient");
      const c2 = x.chart(x.main, "Open interest · 30 j");
      const c3 = x.chart(x.main, "Ratio long / short · 7 j", "1 = équilibre");
      const frPts = fr ? fr.map(f => ({ t: +f.fundingTime, v: +f.fundingRate * 100 })) : [];
      lineChart(c1.box, { series: [{ name: "Funding", color: "var(--btc)", pts: frPts }], bars: true, barColors: ["var(--btc)", "var(--macro)"], fmt: v => (v > 0 ? "+" : "") + fmt(v, 4) + " %", axisFmt: v => fmt(v, 3) + " %" });
      const oiPts = oiD ? oiD.map(o => ({ t: +o.timestamp, v: +o.sumOpenInterestValue })) : [];
      lineChart(c2.box, { series: [{ name: "OI", color: "var(--eth)", pts: oiPts }], fmt: money, axisFmt: v => fmt(v / 1e9, 1) + " Md" });
      lineChart(c3.box, { series: [
        { name: "Comptes (tous)", color: "var(--stable)", pts: ls ? ls.map(o => ({ t: +o.timestamp, v: +o.longShortRatio })) : [], area: false },
        { name: "Top traders (positions)", color: "var(--warn)", pts: top ? top.map(o => ({ t: +o.timestamp, v: +o.longShortRatio })) : [] },
      ], fmt: v => fmt(v, 2), refs: [{ v: 1 }], legend: c3.legend });

      const f = prem ? +prem.lastFundingRate * 100 : frPts.length ? last(frPts).v : NaN;
      const avgF = n => frPts.slice(-n).reduce((s, p) => s + p.v, 0) / Math.min(n, frPts.length);
      const oiNow = oiPts.length ? last(oiPts).v : NaN, oi7 = oiPts.length > 7 ? chg(oiNow, oiPts[oiPts.length - 8].v) : NaN;
      const oi24 = oiH && oiH.length > 1 ? chg(+last(oiH).sumOpenInterestValue, +oiH[0].sumOpenInterestValue) : NaN;
      const dp = D ? toPts(D) : null, p7 = dp ? chg(last(dp).v, atDaysAgo(dp, 7).v) : 0;
      let lbl, tone, txt;
      if (oi7 > 5 && f > .01) [lbl, tone, txt] = ["LEVIER EN HAUSSE", "warn", "L'open interest grimpe et les longs paient le funding : le levier s'accumule côté acheteur. Une baisse rapide pourrait déclencher des liquidations en chaîne."];
      else if (oi7 < -5 && p7 < 0) [lbl, tone, txt] = ["PURGE DU LEVIER", "up", "L'open interest recule avec le prix : les positions à levier sont liquidées ou fermées. Ces purges marquent souvent des creux locaux."];
      else if (f < 0 && p7 > 0) [lbl, tone, txt] = ["SHORTS PIÉGÉS ?", "up", "Le funding est négatif alors que le prix monte : les vendeurs à découvert paient et pourraient être forcés de racheter (short squeeze)."];
      else if (f > .03) [lbl, tone, txt] = ["EUPHORIE DES LONGS", "down", "Funding très élevé : les acheteurs paient cher pour garder leurs positions, signe d'excès de confiance."];
      else [lbl, tone, txt] = ["POSITIONNEMENT ÉQUILIBRÉ", "neutral", "Pas d'excès de levier marqué : le marché n'est ni surchargé à l'achat ni à la vente."];
      x.reading(lbl, tone, [txt, `Open interest 7 j : <b>${Number.isFinite(oi7) ? pct(oi7, 1) : "—"}</b> · prix 7 j : <b>${pct(p7, 1)}</b> · funding : <b>${Number.isFinite(f) ? (f > 0 ? "+" : "") + fmt(f, 4) + " %" : "—"}</b>.`]);
      const lsNow = ls && ls.length ? last(ls) : null, topNow = top && top.length ? last(top) : null;
      const buy = tk ? tk.reduce((s, r) => s + +r.buyVol, 0) : 0, sell = tk ? tk.reduce((s, r) => s + +r.sellVol, 0) : 0;
      x.kv("Chiffres clés", [
        Number.isFinite(f) && ["Funding actuel (8 h)", (f > 0 ? "+" : "") + fmt(f, 4) + " %"],
        Number.isFinite(f) && ["Annualisé", pct(f * 3 * 365, 1)],
        frPts.length && ["Moyenne 7 j / 30 j", `${fmt(avgF(21), 4)} % · ${fmt(avgF(90), 4)} %`],
        prem && ["Prochain funding", "dans " + countdown(+prem.nextFundingTime - Date.now())],
        prem && ["Prix mark / index", `${usd(+prem.markPrice)} · ${usd(+prem.indexPrice)}`],
        prem && ["Écart perp / spot", fmt((+prem.markPrice / +prem.indexPrice - 1) * 1e4, 1) + " pb"],
        Number.isFinite(oiNow) && ["Open interest", money(oiNow)],
        Number.isFinite(oi24) && ["OI 24 h", pctH(oi24)],
        Number.isFinite(oi7) && ["OI 7 j", pctH(oi7)],
        oiPts.length > 1 && ["OI 30 j", pctH(chg(oiNow, oiPts[0].v))],
        lsNow && ["Comptes long / short", `${fmt(+lsNow.longAccount * 100, 1)} % · ${fmt(+lsNow.shortAccount * 100, 1)} %`],
        topNow && ["Top traders (positions)", `ratio ${fmt(+topNow.longShortRatio, 2)}`],
        tk && sell && ["Achats / ventes agressifs 24 h", `ratio ${fmt(buy / sell, 2)}`],
      ]);
      x.levels("Funding : repères", [
        ["< 0 %", "Les shorts paient : pessimisme, carburant pour un rebond", "info", f < 0],
        ["0 – 0,01 %", "Neutre (0,01 % = taux de base)", "neutral", f >= 0 && f <= .012],
        ["0,01 – 0,03 %", "Longs chargés", "warn", f > .012 && f <= .03],
        ["> 0,03 %", "Surchauffe : risque de purge", "down", f > .03],
      ]);
      x.text("Comment le lire", [
        "<b>Funding</b> : paiement échangé toutes les 8 h entre acheteurs et vendeurs de contrats perpétuels pour coller au prix spot. Positif = les acheteurs paient.",
        "<b>Open interest</b> : valeur totale des contrats ouverts, donc le levier présent sur le marché. OI qui monte vite + prix qui stagne = tension.",
        "<b>Long / short</b> : les comptes « tous » reflètent la foule, les « top traders » les plus gros comptes. Quand ils divergent, les gros comptes ont souvent raison.",
      ]);
    },
  };

  /* ---------- Dominance ---------- */
  DETAILS.dom = {
    kicker: "Parts de marché · CoinGecko & Binance", title: "Dominance et rotation du capital",
    async render(x) {
      const { g } = await gecko();
      const p = g.market_cap_percentage;
      const ek = await cached("ethbtc1000", 10 * 60e3, () => klines("ETHBTC", "1d", 1000));
      const ep = toPts(ek), ema50 = rollMA(ep, 50), ema200 = rollMA(ep, 200);
      const entries = Object.entries(p).sort((a, b) => b[1] - a[1]);
      const others = Math.max(0, 100 - entries.reduce((s, [, v]) => s + v, 0));
      const mx = entries[0][1];
      const COL = { btc: "var(--btc)", eth: "var(--eth)" };
      x.section(x.main, "Dominance par actif · top 10", `<div class="tbl">${entries.concat([["autres", others]]).map(([k, v], i) => `
        <div style="grid-template-columns:62px 1fr 58px;animation-delay:${.3 + i * .05}s"><span><b>${k.toUpperCase()}</b></span><span class="hb"><i class="grow-in" style="width:0;background:${COL[k] || (STABLES.has(k) ? "var(--stable)" : "var(--other)")}" data-w="${v / mx * 100}"></i></span><span class="n">${fmt(v, 2)} %</span></div>`).join("")}</div>`);
      requestAnimationFrame(() => setTimeout(() => x.main.querySelectorAll("[data-w]").forEach(el => el.style.width = el.dataset.w + "%"), 200));
      const c = x.chart(x.main, "ETH / BTC");
      const DAYS = { "3m": 92, "1a": 365, "max": 1000 };
      x.tabs([["3m", "3 mois"], ["1a", "1 an"], ["max", "Max"]], "1a", id => {
        lineChart(c.box, { series: [{ name: "ETH/BTC", color: "var(--eth)", pts: sinceDays(ep, DAYS[id]) }, { name: "MM50", color: "var(--macro)", pts: sinceDays(ema50, DAYS[id]), width: 1.6 }, { name: "MM200", color: "var(--btc)", pts: sinceDays(ema200, DAYS[id]), width: 1.6 }], fmt: v => fmt(v, 5), legend: c.legend });
      });
      const e = last(ep).v, eUp = e > last(ema50).v, alt = S.altIdx ?? 0;
      const phase = alt >= 75 ? 4 : alt >= 50 ? 3 : eUp ? 2 : 1;
      const stab = Object.entries(p).filter(([k]) => STABLES.has(k)).reduce((s, [, v]) => s + v, 0);
      const txt = {
        1: "Le capital se concentre sur <b>Bitcoin</b> : dominance élevée et ETH/BTC sous sa MM50. Les altcoins sous-performent.",
        2: "<b>ETH/BTC</b> repasse au-dessus de sa MM50 : le capital commence à tourner vers Ethereum.",
        3: "Plus de la moitié des grands altcoins battent BTC : la rotation s'étend aux <b>large caps</b>.",
        4: "Plus de 75 % des altcoins battent BTC : <b>altseason</b> en cours, phase la plus spéculative.",
      }[phase];
      x.reading(`PHASE ${phase} / 4`, phase === 1 ? "warn" : phase === 4 ? "down" : "up", [txt]);
      x.section(x.side, "Cycle de rotation habituel", `<div class="steps">${["Bitcoin", "Ethereum", "Large caps", "Altseason"].map((s, i) => `<div class="step ${i + 1 === phase ? "on" : i + 1 < phase ? "done" : ""}"><b>${i + 1}</b>${s}</div>`).join("")}</div>`);
      x.kv("Chiffres clés", [
        ["Capitalisation totale", money(g.total_market_cap.usd)],
        ["Variation 24 h", pctH(g.market_cap_change_percentage_24h_usd, 2)],
        ["Volume 24 h", money(g.total_volume.usd)],
        ["Dominance BTC", fmt(p.btc, 2) + " %"],
        ["Dominance ETH", fmt(p.eth, 2) + " %"],
        ["Dominance stablecoins", fmt(stab, 2) + " %"],
        ["ETH / BTC", fmt(e, 5)],
        ["ETH / BTC 7 j · 30 j · 90 j", `${pctH(chg(e, atDaysAgo(ep, 7).v))} · ${pctH(chg(e, atDaysAgo(ep, 30).v))} · ${pctH(chg(e, atDaysAgo(ep, 90).v))}`],
        ["Cryptos suivies", fmt(g.active_cryptocurrencies, 0)],
      ]);
      x.text("Comment le lire", [
        "Le capital crypto circule souvent par étapes : d'abord <b>Bitcoin</b>, puis <b>Ethereum</b>, puis les grandes capitalisations, et enfin les petites (altseason).",
        "Une <b>dominance des stablecoins</b> qui monte signifie que les investisseurs se mettent à l'abri en cash ; qui baisse, qu'ils réinvestissent.",
      ]);
    },
  };

  /* ---------- Altseason ---------- */
  DETAILS.alt = {
    kicker: "Top 50 altcoins vs Bitcoin · CoinGecko", title: "Qui bat Bitcoin ?",
    async render(x) {
      const { m } = await gecko();
      const btc = m.find(c => c.id === "bitcoin");
      const sec = x.section(x.main, "Performance de chaque altcoin face à BTC", "", "scroll");
      const sideBox = h("div"); sideBox.style.display = "contents"; x.side.appendChild(sideBox);
      const LBL = { "30d": "30 jours", "7d": "7 jours", "24h": "24 heures" };
      x.tabs([["30d", "30 j"], ["7d", "7 j"], ["24h", "24 h"]], "30d", per => {
        const k = "price_change_percentage_" + per + "_in_currency";
        const alts = pickAlts(m, per).sort((a, b) => b[k] - a[k]);
        const b = btc ? btc[k] : 0;
        const beat = alts.filter(c => c[k] > b).length, idx = Math.round(beat / alts.length * 100);
        const rel = alts.map(c => c[k] - b), mx = Math.max(...rel.map(Math.abs), 1);
        sec.innerHTML = `<div class="sub" style="margin-bottom:6px">Ligne centrale = Bitcoin (<b>${pct(b, 1)}</b> sur ${LBL[per]}). Barre verte = fait mieux que BTC.</div><div class="tbl">
          <div class="th" style="grid-template-columns:22px 20px 70px 1fr 62px 62px"><span>#</span><span></span><span>Actif</span><span>vs BTC</span><span class="n">Perf.</span><span class="n">Écart</span></div>
          ${alts.map((c, i) => { const r = rel[i]; return `<div style="grid-template-columns:22px 20px 70px 1fr 62px 62px;animation-delay:${Math.min(i, 20) * .025}s">
            <span class="s">${i + 1}</span>${c.image ? `<img src="${esc(c.image)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.style.visibility='hidden'">` : "<span></span>"}
            <span><b>${esc(c.symbol.toUpperCase())}</b></span>
            <span class="hb mid"><i style="left:${r < 0 ? 50 - Math.abs(r) / mx * 50 : 50}%;width:${Math.abs(r) / mx * 50}%;background:${r > 0 ? "var(--up)" : "var(--down)"}"></i></span>
            <span class="n ${signCls(c[k])}">${pct(c[k], 1)}</span><span class="n ${signCls(r)}">${pct(r, 1)}</span></div>`; }).join("")}</div>`;
        const vals = alts.map(c => c[k]).sort((a, b) => a - b), med = vals[Math.floor(vals.length / 2)];
        const [lbl, tone] = idx >= 75 ? ["ALTSEASON", "up"] : idx <= 25 ? ["SAISON BITCOIN", "warn"] : ["MARCHÉ MIXTE", "neutral"];
        sideBox.innerHTML = "";
        const sx = makeSubCtx(x, sideBox);
        sx.reading(`${lbl} · ${idx}/100`, tone, [`<b>${beat}</b> des ${alts.length} premiers altcoins font mieux que Bitcoin sur ${LBL[per]}.`,
          idx >= 75 ? "Le capital se disperse vers les altcoins : phase spéculative, souvent en fin de cycle." : idx <= 25 ? "Bitcoin capte l'essentiel des flux : les altcoins sous-performent nettement." : "Pas de tendance nette : la sélection d'actifs prime."]);
        sx.kv("Chiffres clés · " + LBL[per], [
          ["Index sur la période", idx + " / 100"],
          ["Altcoins qui battent BTC", `${beat} / ${alts.length}`],
          ["Performance BTC", pctH(b)],
          ["Médiane des altcoins", pctH(med)],
          ["Meilleur", `${alts[0].symbol.toUpperCase()} ${pctH(alts[0][k])}`],
          ["Pire", `${last(alts).symbol.toUpperCase()} ${pctH(last(alts)[k])}`],
        ]);
      });
      x.levels("Repères", [
        ["≥ 75", "Altseason : la majorité des altcoins surperforme", "up"],
        ["26 – 74", "Marché mixte", "neutral"],
        ["≤ 25", "Saison Bitcoin", "warn"],
      ]);
      x.text("Comment le lire", [
        "L'index compte la part des 50 plus gros altcoins (hors stablecoins et jetons « wrapped ») dont la performance dépasse celle de Bitcoin sur la période.",
        "La référence du marché utilise 90 jours ; la version 30 jours réagit plus vite, la version 24 h montre le flux du moment.",
      ]);
    },
  };
  function makeSubCtx(x, parent) {
    return {
      reading(label, tone, ps) { const sec = h("section", "dsec read"); sec.style.setProperty("--tone", TONE[tone] || tone); sec.innerHTML = `<div class="dsec-h"><span>Lecture actuelle</span></div><span class="pill">${label}</span>${ps.map(p => `<p>${p}</p>`).join("")}`; parent.appendChild(sec); },
      kv(title, rows) { x.kv(title, rows, parent); },
    };
  }

  /* ---------- Cycle ---------- */
  DETAILS.cycle = {
    kicker: "Indicateurs de cycle · Bitcoin", title: "Où en est le cycle ?",
    async render(x) {
      const D = await btcDaily(), dp = toPts(D), wp = toPts(S.btcW);
      const ma200 = rollMA(dp, 200), ma111 = rollMA(dp, 111), ma350 = rollMA(dp, 350), wma = rollMA(wp, 200);
      const mayer = dp.map((p, i) => ({ t: p.t, v: p.v / ma200[i].v })).filter(fin);
      const pi2 = ma350.map(p => ({ t: p.t, v: p.v * 2 }));
      const rsiS = rsiSeries(dp).slice(-365);
      const c = x.chart(x.main, "");
      const VIEWS = {
        mayer: () => ({ t: "Mayer Multiple · prix / MM200 jours", cfg: { series: [{ name: "Mayer", color: "var(--btc)", pts: mayer }], fmt: v => fmt(v, 2), refs: [{ v: .8, label: "0,8 · zone d'achat" }, { v: 1, label: "1,0" }, { v: 2.4, label: "2,4 · surchauffe" }], bands: [{ from: 0, to: .8, color: "#22c55e" }, { from: 2.4, to: 5, color: "#ef4444" }] } }),
        pi: () => ({ t: "Pi Cycle Top · MM111 vs 2 × MM350 (log)", cfg: { series: [{ name: "Prix", color: "var(--faint)", pts: dp.slice(349), area: false, width: 1.4 }, { name: "MM111", color: "var(--btc)", pts: ma111.slice(349) }, { name: "2 × MM350", color: "var(--eth)", pts: pi2.slice(349) }], fmt: usd, axisFmt: v => fmt(v / 1000, 0) + " k", log: true } }),
        wma: () => ({ t: "Prix hebdo et MM 200 semaines (log)", cfg: { series: [{ name: "Prix", color: "var(--btc)", pts: wp }, { name: "MM 200 sem.", color: "var(--eth)", pts: wma }], fmt: usd, axisFmt: v => v >= 1000 ? fmt(v / 1000, 0) + " k" : fmt(v, 0), log: true } }),
        rsi: () => ({ t: "RSI 14 jours · 1 an", cfg: { series: [{ name: "RSI", color: "var(--macro)", pts: rsiS, area: false }], fmt: v => fmt(v, 0), yMin: 0, yMax: 100, refs: [{ v: 70, label: "70 · suracheté" }, { v: 30, label: "30 · survendu" }], bands: [{ from: 70, to: 100, color: "#ef4444" }, { from: 0, to: 30, color: "#22c55e" }] } }),
      };
      x.tabs([["mayer", "Mayer"], ["pi", "Pi Cycle"], ["wma", "MM 200 sem."], ["rsi", "RSI"]], "mayer", id => {
        const v = VIEWS[id](); c.title.textContent = v.t; lineChart(c.box, { ...v.cfg, legend: c.legend });
      });
      const price = last(dp).v, my = last(mayer).v, m2y = mayer.slice(-730);
      const pi = last(ma111).v / last(pi2).v, w = last(wma).v, r = last(rsiS).v;
      const HALVING = Date.parse("2024-04-20T00:09:00Z"), dsh = Math.floor((Date.now() - HALVING) / DAY);
      const [lbl, tone] = my > 2.4 || pi > .98 ? ["SURCHAUFFE", "down"] : my > 1.5 ? ["EUPHORIE", "warn"] : my >= 1 ? ["TENDANCE SAINE", "up"] : my >= .8 ? ["SOUS LA MM200", "warn"] : ["ZONE D'ACCUMULATION", "up"];
      x.reading(lbl, tone, [
        `Mayer Multiple à <b>${fmt(my, 2)}</b> : le prix est ${my >= 1 ? pct((my - 1) * 100, 0) + " au-dessus" : pct((1 - my) * 100, 0).replace("+", "") + " en dessous"} de sa moyenne 200 jours.`,
        `Pi Cycle à <b>${fmt(pi * 100, 0)} %</b> du signal de sommet${pi > .9 ? " : zone de vigilance." : " : pas de signal de sommet."}`,
        `<b>${dsh} jours</b> depuis le halving d'avril 2024. Lors des cycles précédents, le sommet est arrivé environ 520 à 550 jours après le halving${dsh > 560 ? " : cette fenêtre est dépassée, et historiquement le creux du marché baissier a suivi environ un an après le sommet." : dsh >= 480 ? " : nous sommes dans cette fenêtre." : "."}`,
      ]);
      x.kv("Chiffres clés", [
        ["Mayer Multiple", fmt(my, 2)],
        ["Mayer max / min 2 ans", `${fmt(Math.max(...m2y.map(p => p.v)), 2)} · ${fmt(Math.min(...m2y.map(p => p.v)), 2)}`],
        ["MM200 jours", usd(last(ma200).v)],
        ["MM111 / 2 × MM350", `${usd(last(ma111).v)} · ${usd(last(pi2).v)}`],
        ["Pi Cycle (100 % = signal)", fmt(pi * 100, 1) + " %"],
        ["MM 200 semaines", `${usd(w)} <span class="muted">(${pct(chg(price, w), 0)})</span>`],
        ["RSI 14 jours", fmt(r, 1)],
        ["Jours depuis le halving", fmt(dsh, 0)],
      ]);
      x.levels("Mayer Multiple : repères", [
        ["< 0,8", "Zone d'achat historique (creux de cycle)", "up", my < .8],
        ["0,8 – 1,0", "Sous la MM200 : marché faible", "warn", my >= .8 && my < 1],
        ["1,0 – 1,5", "Tendance haussière saine", "up", my >= 1 && my < 1.5],
        ["1,5 – 2,4", "Euphorie", "warn", my >= 1.5 && my < 2.4],
        ["> 2,4", "Surchauffe (sommets de cycle passés)", "down", my >= 2.4],
      ]);
      x.text("Comment le lire", [
        "<b>Mayer Multiple</b> : écart entre le prix et sa moyenne 200 jours. Les sommets de cycle ont dépassé 2,4 ; les creux sont passés sous 0,8.",
        "<b>Pi Cycle Top</b> : quand la MM111 croise au-dessus du double de la MM350, cela a signalé les sommets de 2013, 2017 et 2021 à quelques jours près.",
        "<b>MM 200 semaines</b> : plancher historique des marchés baissiers ; BTC n'a passé que de courtes périodes en dessous.",
      ]);
    },
  };

  /* ---------- Liquidité & agenda ---------- */
  DETAILS.liq = {
    kicker: "Stablecoins · Fed · réseau Bitcoin", title: "Liquidité et calendrier",
    async render(x) {
      const [st, list, fees, diff] = await Promise.all([
        stablesAll(),
        cached("stableList", 30 * 60e3, () => getJSON("https://stablecoins.llama.fi/stablecoins?includePrices=false")).catch(() => null),
        getJSON("https://mempool.space/api/v1/fees/recommended").catch(() => null),
        getJSON("https://mempool.space/api/v1/difficulty-adjustment").catch(() => null),
      ]);
      const pts = st.map(q => ({ t: +q.date * 1000, v: stableTotal(q) }));
      const c = x.chart(x.main, "Offre totale de stablecoins");
      const DAYS = { "90j": 90, "1a": 365, "max": 1e5 };
      x.tabs([["90j", "90 j"], ["1a", "1 an"], ["max", "Max"]], "1a", id => {
        lineChart(c.box, { series: [{ name: "Stablecoins", color: "var(--stable)", pts: sinceDays(pts, DAYS[id]) }], fmt: money, axisFmt: v => fmt(v / 1e9, 0) + " Md" });
      });
      if (list && list.peggedAssets) {
        const g = a => (a && a.peggedUSD) || 0;
        const top = list.peggedAssets.filter(a => g(a.circulating) > 0).sort((a, b) => g(b.circulating) - g(a.circulating)).slice(0, 8);
        const tot = last(pts).v;
        x.section(x.main, "Principaux stablecoins", `<div class="tbl">
          <div class="th" style="grid-template-columns:64px 1fr 76px 58px 58px"><span>Actif</span><span>Part</span><span class="n">Offre</span><span class="n">7 j</span><span class="n">30 j</span></div>
          ${top.map((a, i) => { const now = g(a.circulating), w7 = g(a.circulatingPrevWeek), m1 = g(a.circulatingPrevMonth); return `<div style="grid-template-columns:64px 1fr 76px 58px 58px;animation-delay:${.3 + i * .05}s">
            <span><b>${esc(a.symbol)}</b></span><span class="hb"><i style="width:${now / tot * 100}%;background:var(--stable)"></i></span><span class="n">${money(now)}</span>
            <span class="n">${w7 ? pctH(chg(now, w7)) : "—"}</span><span class="n">${m1 ? pctH(chg(now, m1)) : "—"}</span></div>`; }).join("")}</div>`);
      }
      const v = last(pts).v, c30 = chg(v, atDaysAgo(pts, 30).v);
      const [lbl, tone, txt] = c30 > 2 ? ["LIQUIDITÉ ENTRANTE", "up", "L'offre de stablecoins progresse vite : de nouveaux capitaux arrivent dans l'écosystème, prêts à être investis."]
        : c30 > 0 ? ["LIQUIDITÉ STABLE", "neutral", "L'offre progresse lentement : la liquidité est présente mais n'accélère pas."]
        : ["LIQUIDITÉ SORTANTE", "down", "L'offre de stablecoins recule : des capitaux quittent la crypto."];
      x.reading(lbl, tone, [txt]);
      x.kv("Stablecoins", [
        ["Offre totale", money(v)],
        ["7 jours", pctH(chg(v, atDaysAgo(pts, 7).v), 2)],
        ["30 jours", pctH(c30, 2)],
        ["90 jours", pctH(chg(v, atDaysAgo(pts, 90).v), 2)],
        ["1 an", pctH(chg(v, atDaysAgo(pts, 365).v), 1)],
      ]);
      const now = Date.now(), next = FOMC.map(Date.parse).find(t => t > now);
      x.section(x.side, "Réunions FOMC 2026 · décisions de la Fed", `<div class="fomc">${FOMC.map(d => { const t = Date.parse(d); return `<span class="${t < now ? "past" : t === next ? "next" : ""}">${dateFR(t, { day: "numeric", month: "short" })}</span>`; }).join("")}</div>
        <div class="sub" style="margin-top:8px">${next ? `Prochaine décision le <b>${new Date(next).toLocaleString("fr-FR", { weekday: "long", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" })}</b>, dans ${countdown(next - now)}.` : "Dates 2027 à ajouter dans index.html (tableau FOMC)."}</div>`);
      const hgt = S.height || 0, nextH = Math.ceil((hgt + 1) / 210000) * 210000, left = nextH - hgt, prog = (hgt - (nextH - 210000)) / 210000 * 100;
      const epoch = Math.floor(hgt / 210000), reward = 50 / 2 ** epoch;
      x.section(x.side, "Réseau Bitcoin", `<div class="dkv">
        ${hgt ? `<span>Hauteur de bloc</span><b>${fmt(hgt, 0)}</b><span>Prochain halving</span><b>bloc ${fmt(nextH, 0)} · ≈ ${dateFR(now + left * 600e3, { month: "short", year: "numeric" })}</b>
        <span>Blocs restants</span><b>${fmt(left, 0)} (≈ ${fmt(left / 144, 0)} j)</b><span>Récompense</span><b>${fmt(reward, 3)} → ${fmt(reward / 2, 4)} BTC</b>` : ""}
        ${diff ? `<span>Ajustement de difficulté</span><b>${pct(diff.difficultyChange, 2)} · dans ${fmt(diff.remainingBlocks, 0)} blocs</b>` : ""}
        ${fees ? `<span>Frais (rapide · 30 min · 1 h)</span><b>${fees.fastestFee} · ${fees.halfHourFee} · ${fees.hourFee} sat/vB</b>` : ""}
        </div>${hgt ? `<div class="sub" style="margin-top:6px">Progression de l'époque actuelle : ${fmt(prog, 1)} %</div><div class="dprog"><i data-w="${prog}"></i></div>` : ""}`);
      setTimeout(() => x.side.querySelectorAll(".dprog i").forEach(i => i.style.width = i.dataset.w + "%"), 300);
      x.text("Comment le lire", [
        "Les <b>stablecoins</b> sont la « poudre sèche » de la crypto : leur offre qui augmente précède souvent la hausse des prix, car ce sont ces dollars qui achètent BTC et les altcoins.",
        "Les <b>décisions de la Fed</b> (taux, discours de Powell) font souvent bouger le dollar et la crypto le soir même : attention à la volatilité autour de 20 h (heure de Paris).",
        "Le <b>halving</b> divise par deux la nouvelle offre de BTC tous les 210 000 blocs (≈ 4 ans) ; il structure le cycle haussier/baissier depuis 2012.",
      ]);
    },
  };

  window.openDetail = openDetail;
  window.closeDetail = closeDetail;
})();

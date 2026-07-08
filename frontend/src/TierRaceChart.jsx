import { useEffect, useMemo, useRef, useState } from 'react';

// TierRaceChart — 21-year walk-forward, $100k, RigaCap Preserver vs Maximizer
// vs the S&P 500. Log-scale equity curves that draw left-to-right on scroll-in.
// Where the regime engine has the strategy DEFENSIVE (de-risked / stepping back),
// the tier lines go DASHED and the period is lightly shaded — the "holding /
// in-cash" story. Animated flags mark the major exits as the draw passes them.
// A Preserve / Both / Maximize control (echoing the risk dial) emphasizes one
// tier. Hover to scrub any date. Data: /track-record-curves.json.

const GREEN = '#2D5F3F', CLARET = '#7A2430', SPYC = '#9A927F';
const INK = '#141210', MUTE = '#5A544E', LIGHT = '#8A8279', RULE = '#DDD5C7';

const SERIES = [
  { key: 'preserver', label: 'RigaCap Preserver', color: GREEN },
  { key: 'maximizer', label: 'RigaCap Maximizer', color: CLARET },
  { key: 'spy',       label: 'S&P 500',           color: SPYC },
];

// A few major de-risk moments to flag (must exist near a data date).
const FLAGS = [
  { date: '2008-09-02', label: 'To cash · 2008' },
  { date: '2020-03-05', label: 'COVID de-risk' },
  { date: '2022-06-13', label: '2022 bear' },
];

// Kept few + wide for a clean read; the fine-grained defensive stretches show
// as dashed segments on the lines themselves (from data.defensive).
const ERAS = [
  { from: '2008-08-01', to: '2009-06-01' },
  { from: '2020-02-15', to: '2020-05-01' },
  { from: '2022-01-01', to: '2022-12-01' },
];

const VB_W = 960, VB_H = 520;
const PAD = { l: 14, r: 104, t: 40, b: 34 };
const PLOT_W = VB_W - PAD.l - PAD.r;
const PLOT_H = VB_H - PAD.t - PAD.b;
const DRAW_MS = 2600;

const fmtMoney = (v) => (v >= 1e6 ? `$${(v / 1e6).toFixed(2)}M` : `$${Math.round(v / 1000)}k`);

export default function TierRaceChart() {
  const [data, setData] = useState(null);
  const [mode, setMode] = useState('both'); // preserver | both | maximizer
  const [prog, setProg] = useState(0);       // 0..1 draw progress
  const [hover, setHover] = useState(null);  // scrub index or null
  const [rw, setRw] = useState(VB_W);
  const boxRef = useRef(), svgRef = useRef(), mountedRef = useRef(true), startedRef = useRef(false);

  useEffect(() => {
    fetch('/track-record-curves.json').then((r) => r.json()).then(setData).catch(() => {});
  }, []);

  useEffect(() => { mountedRef.current = true; return () => { mountedRef.current = false; }; }, []);

  const G = useMemo(() => {
    if (!data) return null;
    const n = data.dates.length;
    let vMin = Infinity, vMax = -Infinity;
    for (const s of SERIES) for (const v of data[s.key]) { if (v < vMin) vMin = v; if (v > vMax) vMax = v; }
    const lMin = Math.log(vMin * 0.9), lMax = Math.log(vMax * 1.08);
    const X = (i) => PAD.l + (i / (n - 1)) * PLOT_W;
    const Y = (v) => PAD.t + (1 - (Math.log(v) - lMin) / (lMax - lMin)) * PLOT_H;
    const P = (i, v) => X(i).toFixed(1) + ',' + Y(v).toFixed(1);

    // defensive spans → per-point boolean
    const def = (data.defensive || []);
    const isDef = (ds) => def.some(([a, b]) => ds >= a && ds <= b);
    // Split each tier into solid (offensive) / dashed (defensive) segments,
    // carrying the boundary point so the line stays continuous.
    const segsFor = (key) => {
      const a = data[key]; const out = []; let cur = null, curDef = null;
      for (let i = 0; i < a.length; i++) {
        const d = isDef(data.dates[i]);
        if (curDef === null) { cur = { dashed: d, d: 'M' + P(i, a[i]) + ' ' }; curDef = d; }
        else if (d !== curDef) { cur.d += 'L' + P(i, a[i]) + ' '; out.push(cur); cur = { dashed: d, d: 'M' + P(i, a[i]) + ' ' }; curDef = d; }
        else cur.d += 'L' + P(i, a[i]) + ' ';
      }
      if (cur) out.push(cur);
      return out;
    };
    const segs = { preserver: segsFor('preserver'), maximizer: segsFor('maximizer') };
    let spy = '';
    for (let i = 0; i < n; i++) spy += (i ? 'L' : 'M') + P(i, data[data ? 'spy' : ''][i]) + ' ';

    const ticks = [100000, 250000, 500000, 1000000].filter((v) => v >= vMin * 0.85 && v <= vMax * 1.1);
    const defBands = ERAS.map((e) => {
      const i0 = data.dates.findIndex((d) => d >= e.from); let i1 = data.dates.findIndex((d) => d >= e.to); if (i1 < 0) i1 = n - 1;
      return i0 >= 0 ? { x0: X(i0), x1: X(i1) } : null;
    }).filter(Boolean);
    const yearTicks = []; let last = null;
    for (let i = 0; i < n; i++) { const y = +data.dates[i].slice(0, 4); if (y % 4 === 0 && y !== last) { yearTicks.push({ x: X(i), y }); last = y; } }
    // flags → nearest index + fractional position along the draw
    const flags = FLAGS.map((f) => {
      let idx = data.dates.findIndex((d) => d >= f.date); if (idx < 0) return null;
      return { ...f, i: idx, x: X(idx), frac: idx / (n - 1) };
    }).filter(Boolean);
    return { n, X, Y, segs, spy, ticks, defBands, yearTicks, flags };
  }, [data]);

  // draw-on-scroll — start when the chart enters view, or immediately if it's
  // already on-screen. StrictMode-safe: rAF self-stops via mountedRef.
  useEffect(() => {
    if (!G || startedRef.current) return;
    let obs;
    const startAnim = () => {
      if (startedRef.current) return;
      startedRef.current = true;
      if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) { setProg(1); return; }
      let t0 = null;
      const step = (t) => {
        if (!mountedRef.current) return;
        if (t0 == null) t0 = t;
        const p = Math.min(1, (t - t0) / DRAW_MS);
        setProg(p < 1 ? 1 - Math.pow(1 - p, 3) : 1);
        if (p < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    };
    const el = boxRef.current;
    const r = el && el.getBoundingClientRect();
    if (r && r.top < window.innerHeight * 0.9 && r.bottom > 0) startAnim();
    else if (el) { obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) startAnim(); }, { threshold: 0.15 }); obs.observe(el); }
    const fallback = setTimeout(() => {
      const rr = boxRef.current && boxRef.current.getBoundingClientRect();
      if (rr && rr.top < window.innerHeight && rr.bottom > 0) startAnim();
    }, 1200);
    return () => { if (obs) obs.disconnect(); clearTimeout(fallback); };
  }, [G]);

  useEffect(() => {
    const el = svgRef.current; if (!el) return;
    const m = () => setRw(el.clientWidth || VB_W);
    m(); const ro = new ResizeObserver(m); ro.observe(el);
    return () => ro.disconnect();
  }, [G]);
  const fs = (px) => (px * VB_W / Math.max(rw, 1)).toFixed(1);

  const onMove = (e) => {
    if (!G) return;
    const r = svgRef.current.getBoundingClientRect();
    const cx = ((e.touches ? e.touches[0].clientX : e.clientX) - r.left) / r.width * VB_W;
    const i = Math.round(((cx - PAD.l) / PLOT_W) * (G.n - 1));
    setHover(Math.max(0, Math.min(G.n - 1, i)));
  };

  if (!G) return <div ref={boxRef} className="h-[440px] rounded-lg bg-paper-card animate-pulse" />;

  const emph = (k) => mode === 'both' || mode === k || k === 'spy';
  const clipW = (PAD.l + prog * PLOT_W).toFixed(1);
  const hi = hover != null ? hover : (prog < 1 ? Math.round(prog * (G.n - 1)) : G.n - 1);
  const hiX = G.X(hi);
  const modes = [
    { k: 'preserver', label: 'Preserve', c: GREEN },
    { k: 'both', label: 'Both', c: INK },
    { k: 'maximizer', label: 'Maximize', c: CLARET },
  ];
  const tierOpacity = (k) => (emph(k) ? 1 : 0.12);

  return (
    <div ref={boxRef}>
      {/* Header + dial-style control */}
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-5">
        <div>
          <div className="font-body text-[0.78rem] font-medium tracking-[0.18em] uppercase text-ink-mute mb-1.5">$100,000 · 2007 – 2026 · walk-forward</div>
          <h3 className="font-display text-ink text-[1.5rem] sm:text-[1.75rem] tracking-[-0.02em]" style={{ fontVariationSettings: '"opsz" 96' }}>
            Twenty-one years, <em className="text-claret italic">every regime.</em>
          </h3>
        </div>
        <div className="inline-flex items-center rounded-full border border-rule-dark bg-paper-card p-1 self-start sm:self-auto">
          {modes.map((m) => (
            <button
              key={m.k}
              onClick={() => setMode(m.k)}
              className="px-3.5 sm:px-4 py-1.5 rounded-full text-[0.8rem] font-medium tracking-[0.03em] transition-colors"
              style={mode === m.k ? { background: m.c, color: '#F5F1E8' } : { color: MUTE, background: 'transparent' }}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {/* Chart */}
      <div className="relative rounded-lg border border-rule bg-paper-card overflow-hidden">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${VB_W} ${VB_H}`}
          className="block w-full h-auto touch-none"
          onMouseMove={onMove} onMouseLeave={() => setHover(null)}
          onTouchStart={onMove} onTouchMove={onMove} onTouchEnd={() => setHover(null)}
        >
          <defs>
            <clipPath id="trc-reveal"><rect x="0" y="0" width={clipW} height={VB_H} /></clipPath>
          </defs>

          {/* Defensive-period shading (strategy de-risked) */}
          {G.defBands.map((b, i) => (
            <rect key={i} x={b.x0} y={PAD.t} width={Math.max(1.5, b.x1 - b.x0)} height={PLOT_H} fill="#7A2430" opacity="0.05" />
          ))}

          {/* Y gridlines + $ labels */}
          {G.ticks.map((v) => (
            <g key={v}>
              <line x1={PAD.l} x2={PAD.l + PLOT_W} y1={G.Y(v)} y2={G.Y(v)} stroke={RULE} strokeWidth="1" strokeDasharray="2 4" />
              <text x={PAD.l + PLOT_W + 8} y={G.Y(v) + 4} fontSize={fs(12)} fill={LIGHT} fontFamily="'IBM Plex Mono',monospace">{fmtMoney(v)}</text>
            </g>
          ))}

          {/* X year labels */}
          {G.yearTicks.map((t) => (
            <text key={t.y} x={t.x} y={VB_H - 10} textAnchor="middle" fontSize={fs(12)} fill={LIGHT} fontFamily="'IBM Plex Mono',monospace">{`'${String(t.y).slice(2)}`}</text>
          ))}

          {/* Curves (revealed L→R). Tiers split into solid (offensive) / dashed
              (defensive) segments; S&P stays solid as the benchmark. */}
          <g clipPath="url(#trc-reveal)">
            <path d={G.spy} fill="none" stroke={SPYC} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" opacity={0.7} style={{ transition: 'opacity 0.4s' }} />
            {['preserver', 'maximizer'].filter((k) => emph(k)).map((k) => {
              const color = k === 'preserver' ? GREEN : CLARET;
              return (
                <g key={k}>
                  {G.segs[k].map((s, i) => (
                    <path key={i} d={s.d} fill="none" stroke={color} strokeWidth="2.2" strokeLinejoin="round" strokeLinecap="round"
                      strokeDasharray={s.dashed ? '2 5' : undefined} opacity={s.dashed ? 0.85 : 1} />
                  ))}
                </g>
              );
            })}
          </g>

          {/* Animated de-risk flags — appear as the draw passes them */}
          {G.flags.map((f) => {
            const shown = prog >= f.frac - 0.005;
            return (
              <g key={f.date} opacity={shown ? 0.9 : 0} style={{ transition: 'opacity 0.5s' }}>
                <line x1={f.x} x2={f.x} y1={PAD.t} y2={PAD.t + PLOT_H} stroke={CLARET} strokeWidth="1" strokeDasharray="2 3" opacity="0.35" />
                <circle cx={f.x} cy={PAD.t} r="3" fill={CLARET} />
                <text x={f.x} y={PAD.t - 8} textAnchor="middle" fontSize={fs(11.5)} fontWeight="600" fill={CLARET} fontFamily="'IBM Plex Sans',sans-serif">{f.label}</text>
              </g>
            );
          })}

          {/* End-of-line value chips */}
          {prog >= 1 && SERIES.filter((s) => emph(s.key)).map((s) => {
            const v = data[s.key][G.n - 1];
            return (
              <g key={s.key}>
                <circle cx={G.X(G.n - 1)} cy={G.Y(v)} r="3.5" fill={s.color} />
                <text x={G.X(G.n - 1) + 8} y={G.Y(v) + 4} fontSize={fs(13)} fontWeight="600" fill={s.color} fontFamily="'IBM Plex Mono',monospace">{fmtMoney(v)}</text>
              </g>
            );
          })}

          {/* Hover cursor */}
          {hover != null && (
            <g>
              <line x1={hiX} x2={hiX} y1={PAD.t} y2={PAD.t + PLOT_H} stroke={INK} strokeWidth="1" opacity="0.25" />
              {SERIES.filter((s) => emph(s.key)).map((s) => (
                <circle key={s.key} cx={hiX} cy={G.Y(data[s.key][hi])} r="4" fill={s.color} stroke="#FAF7F0" strokeWidth="1.5" />
              ))}
            </g>
          )}
        </svg>
      </div>

      {/* Readout */}
      <div className="flex flex-wrap items-center gap-x-8 gap-y-3 mt-4">
        <div className="font-mono text-[0.85rem] text-ink-light tabular-nums">{data.dates[hi]}</div>
        {SERIES.filter((s) => emph(s.key)).map((s) => (
          <div key={s.key} className="flex items-center gap-2">
            <span className="inline-block w-3 h-0.5 rounded-full" style={{ background: s.color }} />
            <span className="text-[0.9rem] text-ink-mute">{s.label}</span>
            <span className="font-mono text-[0.95rem] font-semibold tabular-nums" style={{ color: s.color }}>{fmtMoney(data[s.key][hi])}</span>
          </div>
        ))}
      </div>
      <p className="mt-3 text-[0.82rem] text-ink-light leading-relaxed">
        <span className="inline-block align-middle w-5 border-t-2 border-dashed mr-1" style={{ borderColor: CLARET }} /> Dashed = the strategy stepped back (regime defensive). Hover to scrub any date. Both are point-in-time walk-forward simulations &mdash; 2016 onward is survivorship-free; pre-2016 carries a survivorship caveat, disclosed in the <a href="/methodology" className="text-claret underline underline-offset-2 decoration-1">methodology</a>. Not live trading results.
      </p>
    </div>
  );
}

import { useEffect, useMemo, useRef, useState } from 'react';

// PortfolioRace — the human race, 2007-2026 daily, $100k.
// DEFAULT view models real investor behavior: panic-sell after a 25% loss from
// peak, re-enter when the strategy regains the level you sold from ("wait till
// it feels safe" — the classic). Cash years render dashed ("in cash"). The
// finale shows the RANGE of outcomes across three re-entry temperaments
// (wait-till-even / quick re-entry / 12-month cooldown) — raw momentum's
// result is nerve-dependent; RigaCap's is the same number under every rule
// because it never trips the panic threshold. A footnote toggle shows the
// theoretical ("robot") race for full disclosure.

const SERIES_META = [
  { key: 'rigacap', label: 'RigaCap', color: '#7A2430' },
  { key: 'spy', label: 'S&P 500', color: '#8A8578' },
  { key: 'naive', label: 'Raw momentum', color: '#B08D2E' },
];

const ERAS = [
  { from: '2008-09-01', to: '2009-04-01', label: '2008 financial crisis' },
  { from: '2020-02-15', to: '2020-04-15', label: 'COVID' },
  { from: '2022-01-01', to: '2022-11-01', label: '2022 bear' },
];

const PANIC_DD = 0.25;
const RACE_MS = 18000;

// One behavioral path under a given re-entry temperament.
function simulate(vals, reentry) {
  const curve = new Array(vals.length);
  const sells = [];
  const cashSpans = [];
  let units = 1, cash = 0, inv = true, peak = vals[0];
  let exitPeak = 0, exitPrice = 0, outSince = -1;
  for (let i = 0; i < vals.length; i++) {
    const v = vals[i];
    if (inv) {
      if (v > peak) peak = v;
      if (1 - v / peak >= PANIC_DD) {
        cash = units * v; units = 0; inv = false;
        exitPeak = peak; exitPrice = v; outSince = i; sells.push(i);
      }
    } else {
      const ok = reentry === 'peak' ? v >= exitPeak
        : reentry === 'price' ? v >= exitPrice * 1.10
        : i - outSince >= 252;
      if (ok) { units = cash / v; cash = 0; inv = true; peak = v; cashSpans.push([outSince, i]); outSince = -1; }
    }
    curve[i] = units * v + cash;
  }
  if (outSince >= 0) cashSpans.push([outSince, vals.length - 1]);
  return { curve, sells, cashSpans, final: units * vals[vals.length - 1] + cash };
}

const fmtMoney = v => (v >= 1e6 ? `$${(v / 1e6).toFixed(2)}M` : `$${Math.round(v / 1000)}k`);

export default function PortfolioRace() {
  const [data, setData] = useState(null);
  const [cursor, setCursor] = useState(0);
  const [act, setAct] = useState('idle'); // idle | run | scrub | done
  const [robot, setRobot] = useState(false);
  const rafRef = useRef();
  const boxRef = useRef();
  const svgRef = useRef();
  const startedRef = useRef(false);

  useEffect(() => {
    fetch('/portfolio-race.json').then(r => r.json()).then(setData).catch(() => {});
  }, []);

  const C = useMemo(() => {
    if (!data) return null;
    const n = data.dates.length;
    const series = SERIES_META.map(m => {
      const raw = data.series[m.key].value;
      const main = simulate(raw, 'peak'); // the animated path: "wait till even"
      const finals = ['peak', 'price', 'year'].map(r => simulate(raw, r));
      const lo = Math.min(...finals.map(f => f.final));
      const hi = Math.max(...finals.map(f => f.final));
      const sellsRange = [Math.min(...finals.map(f => f.sells.length)), Math.max(...finals.map(f => f.sells.length))];
      return { ...m, raw, ...main, lo, hi, sellsRange, dd: data.series[m.key].dd };
    });
    let vMin = Infinity, vMax = -Infinity;
    for (const s of series) for (const arr of [s.raw, s.curve]) for (const v of arr) {
      if (v < vMin) vMin = v; if (v > vMax) vMax = v;
    }
    const eras = ERAS.map(e => ({
      ...e,
      i0: data.dates.findIndex(d => d >= e.from),
      i1: data.dates.findIndex(d => d >= e.to),
    })).filter(e => e.i0 > 0);
    return { n, series, lMin: Math.log(vMin * 0.93), lMax: Math.log(vMax * 1.07), eras };
  }, [data]);

  useEffect(() => {
    if (!C || startedRef.current || !boxRef.current) return;
    const obs = new IntersectionObserver(([e]) => {
      if (e.isIntersecting && !startedRef.current) { startedRef.current = true; setAct('run'); }
    }, { threshold: 0.35 });
    obs.observe(boxRef.current);
    return () => obs.disconnect();
  }, [C]);

  useEffect(() => {
    if (!C || act !== 'run') return;
    const step = C.n / (RACE_MS / 16.7);
    const tick = () => {
      setCursor(c => {
        const nc = c + step;
        if (nc >= C.n - 1) { setAct('done'); return C.n - 1; }
        rafRef.current = requestAnimationFrame(tick);
        return nc;
      });
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [act, C]);

  if (!C) return null;

  const W = 920, H = 380, PAD_L = 12, PAD_R = 24, PAD_T = 18, PAD_B = 34;
  const { n, series, lMin, lMax, eras } = C;
  const ci = Math.min(Math.floor(cursor), n - 1);
  const x = i => PAD_L + (i / (n - 1)) * (W - PAD_L - PAD_R);
  const y = v => PAD_T + (1 - (Math.log(v) - lMin) / (lMax - lMin)) * (H - PAD_T - PAD_B);

  const path = arr => {
    const stride = Math.max(1, Math.floor(n / 1100));
    let d = `M ${x(0)} ${y(arr[0])}`;
    for (let i = stride; i <= ci; i += stride) d += ` L ${x(i)} ${y(arr[i])}`;
    if (ci % stride !== 0) d += ` L ${x(ci)} ${y(arr[ci])}`;
    return d;
  };

  const activeEra = eras.find(e => ci >= e.i0 && ci <= e.i1);

  // collision-aware label placement: try offsets above/below until the slot
  // clears every visible curve within a small horizontal window AND every
  // previously placed label (labels register as they place, in render order)
  const activeArrs = series.map(s => (robot ? s.raw : s.curve));
  const idxWin = Math.max(2, Math.ceil((16 / (W - PAD_L - PAD_R)) * n));
  const placed = []; // {x, y, hw} of labels already placed this render pass
  const clearY = (i, baseY, preferUp = true, halfW = 14) => {
    const cx = x(i);
    const offs = preferUp ? [-22, 26, -34, 38, -46, 50, -58] : [26, -22, 38, -34, 50, -46, 62];
    let pick = null;
    for (const off of offs) {
      const cand = baseY + off;
      if (cand < PAD_T + 10 || cand > H - PAD_B - 6) continue;
      let ok = true;
      for (const arr of activeArrs) {
        for (let j = Math.max(0, i - idxWin); j <= Math.min(n - 1, i + idxWin); j++) {
          if (Math.abs(y(arr[j]) - cand) < 9) { ok = false; break; }
        }
        if (!ok) break;
      }
      if (ok) {
        for (const p of placed) {
          if (Math.abs(p.y - cand) < 12 && Math.abs(p.x - cx) < p.hw + halfW + 4) { ok = false; break; }
        }
      }
      if (ok) { pick = cand; break; }
    }
    if (pick === null) pick = baseY + offs[0];
    placed.push({ x: cx, y: pick, hw: halfW });
    return pick;
  };
  const yearTicks = [];
  for (let yr = 2008; yr <= 2026; yr += 3) {
    const idx = data.dates.findIndex(d => d.startsWith(String(yr)));
    if (idx > 0) yearTicks.push([idx, yr]);
  }
  const restart = () => { setCursor(0); setRobot(false); setAct('run'); };

  // drag / click anywhere on the chart to scrub to that point in time
  const scrubTo = clientX => {
    const svg = svgRef.current;
    if (!svg) return;
    const r = svg.getBoundingClientRect();
    const xv = ((clientX - r.left) / r.width) * W;
    const frac = Math.max(0, Math.min(1, (xv - PAD_L) / (W - PAD_L - PAD_R)));
    setCursor(frac * (n - 1));
  };
  const onPointerDown = e => {
    cancelAnimationFrame(rafRef.current);
    setAct('scrub');
    e.currentTarget.setPointerCapture?.(e.pointerId);
    scrubTo(e.clientX);
  };
  const onPointerMove = e => {
    if (e.buttons & 1) scrubTo(e.clientX);
  };
  const onPointerUp = () => {
    setCursor(c => {
      if (c >= n - 2) { setAct('done'); return n - 1; }
      return c;
    });
  };

  const title = robot
    ? 'The theoretical race — if a robot held every dip.'
    : act === 'done' ? 'What humans actually collect.'
    : 'Three crashes, one human investor, $100,000.';

  return (
    <div ref={boxRef} className="bg-paper-card border border-rule p-6 sm:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
        <div>
          <div className="font-body text-[0.75rem] font-medium tracking-[0.15em] uppercase text-ink-mute">
            $100,000 · {data.span || '2007–2026'} · walk-forward backtest · panic-sell at −25% modeled
          </div>
          <div className="font-display text-[1.3rem] text-ink mt-0.5" style={{ fontVariationSettings: '"opsz" 96' }}>
            {title}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {act === 'scrub' && (
            <button onClick={() => setAct('run')} className="text-[0.8rem] px-3 py-1.5 border border-rule-dark text-ink-mute hover:text-ink transition-colors">
              ▶ Resume
            </button>
          )}
          {(act === 'done' || act === 'idle' || act === 'scrub') && (
            <button onClick={restart} className="text-[0.8rem] px-3 py-1.5 border border-rule-dark text-ink-mute hover:text-ink transition-colors">
              {act === 'idle' ? '▶ Play' : '↻ Replay'}
            </button>
          )}
        </div>
      </div>

      {/* Scoreboard buckets — money ticks here, not on the chart */}
      <div className="grid grid-cols-3 gap-px bg-rule mb-5">
        {series.map(s => {
          const arr = robot ? s.raw : s.curve;
          const cur = arr[ci];
          const soldSoFar = s.sells.filter(i => i <= ci).length;
          const ddNow = s.dd[ci];
          return (
            <div key={s.key} className="bg-paper p-3 sm:p-4 text-center">
              <div className="font-body text-[0.7rem] font-medium tracking-[0.12em] uppercase mb-1" style={{ color: s.color }}>
                {s.label}
              </div>
              <div className="font-mono text-[1.15rem] sm:text-[1.45rem] font-semibold tabular-nums"
                style={{ color: act === 'done' && !robot && s.key === 'rigacap' ? '#2D5F3F' : '#141210' }}>
                {act === 'done' && !robot && s.sellsRange[1] > 0 ? `${fmtMoney(s.lo)}–${fmtMoney(s.hi)}` : fmtMoney(cur)}
              </div>
              <div className="h-5 text-[0.72rem] font-mono mt-0.5">
                {act === 'done' && !robot ? (
                  s.sellsRange[1] > 0
                    ? <span className="text-ink-light">sold {s.sellsRange[0] === s.sellsRange[1] ? `${s.sellsRange[1]}×` : `${s.sellsRange[0]}–${s.sellsRange[1]}×`} · depends on your nerve</span>
                    : <span style={{ color: '#2D5F3F' }}>never panic-sold · no nerve required</span>
                ) : robot && ddNow < -15 ? (
                  <span style={{ color: '#8F2D3D' }}>▼ {Math.abs(ddNow).toFixed(0)}% from peak</span>
                ) : !robot && soldSoFar > 0 && act === 'run' ? (
                  <span style={{ color: '#8F2D3D' }}>panic-sold {soldSoFar}×</span>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>

      <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} className="w-full cursor-ew-resize select-none"
        style={{ touchAction: 'pan-y' }}
        onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp}
        role="img"
        aria-label="Comparison of $100,000 in RigaCap, the S&P 500, and raw momentum, 2007 to 2026, with panic-selling behavior modeled. Drag to scrub through time.">
        {eras.map(e => (
          <rect key={e.label} x={x(e.i0)} y={PAD_T} width={Math.max(0, x(Math.min(e.i1, ci)) - x(e.i0))}
            height={H - PAD_T - PAD_B} fill="#8F2D3D" opacity={ci >= e.i0 ? 0.06 : 0} />
        ))}
        {yearTicks.map(([idx, yr]) => (
          <g key={yr} opacity={idx <= ci ? 1 : 0.25}>
            <line x1={x(idx)} x2={x(idx)} y1={H - PAD_B} y2={H - PAD_B + 5} stroke="#8A8578" strokeWidth="1" />
            <text x={x(idx)} y={H - 12} textAnchor="middle" fontSize="11" fill="#8A8578" fontFamily="IBM Plex Mono, monospace">{yr}</text>
          </g>
        ))}
        {/* paint order: spy, naive, then rigacap LAST so our line sits on top */}
        {[...series].reverse().map(s => {
          const arr = robot ? s.raw : s.curve;
          const wd = s.key === 'rigacap' ? 2.5 : 1.5;
          return (
            <g key={s.key}>
              <path d={path(arr)} fill="none" stroke={s.color} strokeWidth={wd} strokeLinejoin="round" />
              {!robot && s.cashSpans.filter(([a]) => a <= ci).map(([a, b]) => {
                const bEff = Math.min(b, ci);
                const yc = y(arr[a]);
                const wide = (bEff - a) / n > 0.045;
                return (
                  <g key={`cash-${a}`}>
                    <line x1={x(a)} x2={x(bEff)} y1={yc} y2={yc} stroke="#FBF8F2" strokeWidth={wd + 1.5} />
                    <line x1={x(a)} x2={x(bEff)} y1={yc} y2={yc} stroke={s.color} strokeWidth={wd}
                      strokeDasharray="2 5" opacity="0.55" />
                    {wide && (
                      <text x={(x(a) + x(bEff)) / 2} y={clearY(Math.floor((a + bEff) / 2), yc, s.key !== 'spy', 80)}
                        textAnchor="middle" fontSize="10.5"
                        fontStyle="italic" fill={s.color} opacity="0.85" fontFamily="Fraunces, serif">
                        in cash, waiting to feel safe
                      </text>
                    )}
                  </g>
                );
              })}
              <circle cx={x(ci)} cy={y(arr[ci])} r="3.5" fill={s.color} />
              {!robot && s.sells.filter(i => i <= ci).map(i => {
                const ly = clearY(i, y(arr[i]), true);
                return (
                  <g key={i}>
                    <circle cx={x(i)} cy={y(arr[i])} r="4" fill="none" stroke="#8F2D3D" strokeWidth="1.5" />
                    <line x1={x(i)} x2={x(i)} y1={y(arr[i]) + (ly > y(arr[i]) ? 5 : -5)} y2={ly + (ly > y(arr[i]) ? -9 : 3)}
                      stroke="#8F2D3D" strokeWidth="0.6" opacity="0.5" />
                    <text x={x(i)} y={ly} textAnchor="middle" fontSize="9.5" fill="#8F2D3D" fontFamily="IBM Plex Mono, monospace">sold</text>
                  </g>
                );
              })}
            </g>
          );
        })}
        <line x1={x(ci)} x2={x(ci)} y1={PAD_T} y2={H - PAD_B} stroke="#8A8578" strokeWidth="0.75" strokeDasharray="3 4" opacity="0.6" />
        <text x={Math.min(x(ci), W - 36)} y={PAD_T - 4} textAnchor="middle" fontSize="13" fontWeight="600" fill="#141210" fontFamily="IBM Plex Mono, monospace">
          {data.dates[ci].slice(0, 4)}
        </text>
        {eras.filter(e => ci >= e.i0).map(e => (
          <text key={e.label} x={x(e.i0) + 4} y={PAD_T + 16} fontSize="11.5" fontStyle="italic"
            fill="#8F2D3D" opacity={activeEra?.label === e.label ? 1 : 0.65} fontFamily="Fraunces, serif">
            {e.label}
          </text>
        ))}
      </svg>

      {act === 'done' && !robot && (
        <p className="mt-4 text-[0.95rem] text-ink leading-[1.65]">
          The animated path sells at &minus;25% and re-enters at the old peak; the ranges above span three
          re-entry temperaments, from &ldquo;jumped back in quickly&rdquo; to &ldquo;sat out a year.&rdquo;
          <strong className="font-medium"> Raw momentum's outcome is a lottery on your own nerve &mdash; a spread of
          {' '}{fmtMoney(series[2].lo)} to {fmtMoney(series[2].hi)} across 6&ndash;10 panic-sales.</strong> RigaCap
          collected {fmtMoney(series[0].curve[n - 1])} under every rule, because in twenty-one years it never handed
          you a loss deep enough to trip the panic.
          <em className="font-display italic text-claret"> It removes your own behavior as the biggest risk in the portfolio.</em>
        </p>
      )}

      <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
        <p className="text-[0.8rem] text-ink-light leading-relaxed max-w-[62ch]">
          Walk-forward backtest, price returns; raw momentum gross of costs. 2016+ data survivorship-free; pre-2016 carries
          a survivorship caveat (see <a href="/methodology" className="underline underline-offset-2">methodology</a>).
          Backtested; not a prediction.
        </p>
        <button onClick={() => setRobot(r => !r)}
          className="text-[0.78rem] text-ink-mute underline underline-offset-2 hover:text-ink transition-colors shrink-0">
          {robot ? '← back to the human race' : 'what a robot would have collected →'}
        </button>
      </div>
    </div>
  );
}

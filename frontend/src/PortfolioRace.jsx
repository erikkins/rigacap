import { useEffect, useMemo, useRef, useState } from 'react';

// PortfolioRace — animated $100k race: RigaCap vs S&P 500 vs raw momentum.
// Reads /portfolio-race.json (daily, 2007-2026). Dependency-free SVG +
// requestAnimationFrame. Log-scale y (two decades of compounding).
// "What investors actually do" toggle: panic-sell at 25% drawdown, re-enter
// when the strategy recovers its prior peak — computed from the same series.

const SERIES_META = [
  { key: 'rigacap', label: 'RigaCap', color: '#7A2430', width: 2.5 },
  { key: 'spy', label: 'S&P 500', color: '#8A8578', width: 1.5 },
  { key: 'naive', label: 'Raw momentum', color: '#B08D2E', width: 1.5 },
];

const ERAS = [
  { from: '2008-09-01', to: '2009-04-01', label: '2008 financial crisis' },
  { from: '2020-02-15', to: '2020-04-15', label: 'COVID crash' },
  { from: '2022-01-01', to: '2022-11-01', label: '2022 bear' },
];

const PANIC_DD = 0.25; // behavioral overlay: bail at -25% from own peak

function behavioralCurve(values) {
  // Panic-sell at PANIC_DD below running peak; re-enter when the strategy
  // value recovers to the level at which the investor sold out (peak).
  const out = new Array(values.length);
  let units = 1, cash = 0, invested = true, peak = values[0], exitPeak = 0;
  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    if (invested) {
      if (v > peak) peak = v;
      if (1 - v / peak >= PANIC_DD) {
        cash = units * v; units = 0; invested = false; exitPeak = peak;
      }
    } else if (v >= exitPeak) {
      units = cash / v; cash = 0; invested = true; peak = v;
    }
    out[i] = units * v + cash;
  }
  return out;
}

function fmtMoney(v) {
  if (v >= 1e6) return `$${(v / 1e6).toFixed(2)}M`;
  return `$${Math.round(v / 1000)}k`;
}

export default function PortfolioRace() {
  const [data, setData] = useState(null);
  const [cursor, setCursor] = useState(0);       // index into dates
  const [playing, setPlaying] = useState(false);
  const [behavioral, setBehavioral] = useState(false);
  const [done, setDone] = useState(false);
  const rafRef = useRef();
  const boxRef = useRef();
  const startedRef = useRef(false);

  useEffect(() => {
    fetch('/portfolio-race.json').then(r => r.json()).then(setData).catch(() => {});
  }, []);

  const computed = useMemo(() => {
    if (!data) return null;
    const n = data.dates.length;
    const series = SERIES_META.map(m => {
      const raw = data.series[m.key].value;
      return { ...m, raw, behav: behavioralCurve(raw), dd: data.series[m.key].dd };
    });
    let vMin = Infinity, vMax = -Infinity;
    for (const s of series) {
      for (const arr of [s.raw, s.behav]) {
        for (let i = 0; i < n; i++) {
          if (arr[i] < vMin) vMin = arr[i];
          if (arr[i] > vMax) vMax = arr[i];
        }
      }
    }
    const eras = ERAS.map(e => ({
      ...e,
      i0: data.dates.findIndex(d => d >= e.from),
      i1: data.dates.findIndex(d => d >= e.to),
    })).filter(e => e.i0 > 0);
    return { n, series, lMin: Math.log(vMin * 0.95), lMax: Math.log(vMax * 1.05), eras };
  }, [data]);

  // autostart when scrolled into view
  useEffect(() => {
    if (!computed || startedRef.current || !boxRef.current) return;
    const obs = new IntersectionObserver(([e]) => {
      if (e.isIntersecting && !startedRef.current) {
        startedRef.current = true;
        setPlaying(true);
      }
    }, { threshold: 0.35 });
    obs.observe(boxRef.current);
    return () => obs.disconnect();
  }, [computed]);

  useEffect(() => {
    if (!playing || !computed) return;
    const DURATION_MS = 24000; // ~24s for the full span
    const step = computed.n / (DURATION_MS / 16.7);
    const tick = () => {
      setCursor(c => {
        const nc = c + step;
        if (nc >= computed.n - 1) { setPlaying(false); setDone(true); return computed.n - 1; }
        rafRef.current = requestAnimationFrame(tick);
        return nc;
      });
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [playing, computed]);

  if (!computed) return null;

  const W = 920, H = 420, PAD_L = 14, PAD_R = 118, PAD_T = 24, PAD_B = 36;
  const { n, series, lMin, lMax, eras } = computed;
  const ci = Math.min(Math.floor(cursor), n - 1);
  const x = i => PAD_L + (i / (n - 1)) * (W - PAD_L - PAD_R);
  const y = v => PAD_T + (1 - (Math.log(v) - lMin) / (lMax - lMin)) * (H - PAD_T - PAD_B);
  const yearOf = i => data.dates[Math.min(i, n - 1)].slice(0, 4);

  const path = arr => {
    const stride = Math.max(1, Math.floor(n / 1200));
    let d = `M ${x(0)} ${y(arr[0])}`;
    for (let i = stride; i <= ci; i += stride) d += ` L ${x(i)} ${y(arr[i])}`;
    if (ci % stride !== 0) d += ` L ${x(ci)} ${y(arr[ci])}`;
    return d;
  };

  const activeEra = eras.find(e => ci >= e.i0 && ci <= e.i1);
  const yearTicks = [];
  for (let yr = 2008; yr <= 2026; yr += 3) {
    const idx = data.dates.findIndex(d => d.startsWith(String(yr)));
    if (idx > 0) yearTicks.push([idx, yr]);
  }

  const restart = () => { setCursor(0); setDone(false); setPlaying(true); };

  return (
    <div ref={boxRef} className="bg-paper-card border border-rule p-6 sm:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div>
          <div className="font-body text-[0.75rem] font-medium tracking-[0.15em] uppercase text-ink-mute">
            $100,000 · {data.span || '2007–2026'} · walk-forward backtest
          </div>
          <div className="font-display text-[1.3rem] text-ink mt-0.5" style={{ fontVariationSettings: '"opsz" 96' }}>
            {behavioral ? 'What investors actually collect.' : 'Two decades, three crashes, one survivor.'}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={() => setBehavioral(b => !b)}
            className={`text-[0.8rem] px-3 py-1.5 border transition-colors ${behavioral ? 'bg-claret text-paper border-claret' : 'border-rule-dark text-ink-mute hover:text-ink'}`}>
            {behavioral ? '✓ Panic-selling at −25%' : 'What investors actually do →'}
          </button>
          <button onClick={done ? restart : () => setPlaying(p => !p)}
            className="text-[0.8rem] px-3 py-1.5 border border-rule-dark text-ink-mute hover:text-ink transition-colors">
            {done ? '↻ Replay' : playing ? '❚❚' : '▶'}
          </button>
        </div>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img"
        aria-label="Animated comparison of $100,000 invested in RigaCap, the S&P 500, and raw momentum, 2007 to 2026">
        {/* era shading */}
        {eras.map(e => (
          <rect key={e.label} x={x(e.i0)} y={PAD_T} width={Math.max(0, x(Math.min(e.i1, ci)) - x(e.i0))}
            height={H - PAD_T - PAD_B} fill="#8F2D3D" opacity={ci >= e.i0 ? 0.06 : 0} />
        ))}
        {/* year ticks */}
        {yearTicks.map(([idx, yr]) => (
          <g key={yr} opacity={idx <= ci ? 1 : 0.25}>
            <line x1={x(idx)} x2={x(idx)} y1={H - PAD_B} y2={H - PAD_B + 5} stroke="#8A8578" strokeWidth="1" />
            <text x={x(idx)} y={H - 12} textAnchor="middle" fontSize="11" fill="#8A8578" fontFamily="IBM Plex Mono, monospace">{yr}</text>
          </g>
        ))}
        {/* lines + endpoint labels */}
        {series.map(s => {
          const arr = behavioral ? s.behav : s.raw;
          const cur = arr[ci];
          const ddNow = s.dd[ci];
          const inDrawdown = ddNow < -15;
          return (
            <g key={s.key}>
              <path d={path(arr)} fill="none" stroke={s.color} strokeWidth={s.width} strokeLinejoin="round" />
              <circle cx={x(ci)} cy={y(cur)} r="3.5" fill={s.color} />
              <text x={x(ci) + 8} y={y(cur) - (s.key === 'rigacap' ? 6 : -4)} fontSize="12.5"
                fontWeight={s.key === 'rigacap' ? 700 : 400} fill={s.color} fontFamily="IBM Plex Mono, monospace">
                {s.label} {fmtMoney(cur)}
              </text>
              {!behavioral && inDrawdown && (
                <text x={x(ci) + 8} y={y(cur) + 12} fontSize="10.5" fill="#8F2D3D" fontFamily="IBM Plex Mono, monospace">
                  ▼ {Math.abs(ddNow).toFixed(0)}% from peak
                </text>
              )}
            </g>
          );
        })}
        {/* cursor + era caption */}
        <line x1={x(ci)} x2={x(ci)} y1={PAD_T} y2={H - PAD_B} stroke="#8A8578" strokeWidth="0.75" strokeDasharray="3 4" opacity="0.6" />
        <text x={x(ci)} y={PAD_T - 8} textAnchor="middle" fontSize="13" fontWeight="600" fill="#141210" fontFamily="IBM Plex Mono, monospace">{yearOf(ci)}</text>
        {activeEra && (
          <text x={x(activeEra.i0)} y={PAD_T + 16} fontSize="12" fontStyle="italic" fill="#8F2D3D" fontFamily="Fraunces, serif">
            {activeEra.label}
          </text>
        )}
      </svg>

      {done && (
        <div className="mt-5 pt-5 border-t border-rule grid sm:grid-cols-3 gap-4">
          {series.map(s => {
            // worst_dd_true: rigacap's line is sampled at period boundaries, so its
            // sampled dd understates the true daily worst — use the daily figure.
            const worst = data.series[s.key].worst_dd_true ?? Math.min(...s.dd);
            return (
              <div key={s.key} className="text-[0.9rem]">
                <span className="font-medium" style={{ color: s.color }}>{s.label}</span>
                <span className="text-ink-mute"> · worst drop </span>
                <span className="font-mono font-semibold" style={{ color: worst < -30 ? '#8F2D3D' : '#2D5F3F' }}>
                  {worst.toFixed(0)}%
                </span>
              </div>
            );
          })}
        </div>
      )}

      <p className="mt-4 text-[0.8rem] text-ink-light leading-relaxed">
        Walk-forward backtest, price returns; raw momentum gross of costs. 2016+ data survivorship-free; pre-2016 carries a
        survivorship caveat (see <a href="/methodology" className="underline underline-offset-2">methodology</a>). The
        “what investors actually do” view sells each strategy after a 25% loss from its peak and re-enters at recovery —
        the drawdown you can hold through determines the return you actually collect. Backtested; not a prediction.
      </p>
    </div>
  );
}

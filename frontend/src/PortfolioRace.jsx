import { useEffect, useMemo, useRef, useState } from 'react';

// PortfolioRace — two-act animated $100k race, 2007-2026 daily.
// Act 1: the theoretical race (raw momentum "wins").
// Act 2: the same 20 years with human behavior — every strategy is panic-sold
//        after a 25% loss from its peak and re-bought at recovery. RigaCap never
//        trips; the others get gutted. Fixed scoreboard on top (no labels
//        chasing the line heads), lines are clean strokes with end dots.

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
const ACT1_MS = 19000;
const ACT2_MS = 13000;
const INTERLUDE_MS = 2600;

function behavioral(values) {
  const out = new Array(values.length);
  const sells = [];
  let units = 1, cash = 0, invested = true, peak = values[0], exitPeak = 0;
  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    if (invested) {
      if (v > peak) peak = v;
      if (1 - v / peak >= PANIC_DD) {
        cash = units * v; units = 0; invested = false; exitPeak = peak; sells.push(i);
      }
    } else if (v >= exitPeak) {
      units = cash / v; cash = 0; invested = true; peak = v;
    }
    out[i] = units * v + cash;
  }
  return { curve: out, sells };
}

const fmtMoney = v => (v >= 1e6 ? `$${(v / 1e6).toFixed(2)}M` : `$${Math.round(v / 1000)}k`);

export default function PortfolioRace() {
  const [data, setData] = useState(null);
  const [cursor, setCursor] = useState(0);
  const [act, setAct] = useState('idle'); // idle | one | interlude | two | done
  const rafRef = useRef();
  const boxRef = useRef();
  const startedRef = useRef(false);

  useEffect(() => {
    fetch('/portfolio-race.json').then(r => r.json()).then(setData).catch(() => {});
  }, []);

  const C = useMemo(() => {
    if (!data) return null;
    const n = data.dates.length;
    const series = SERIES_META.map(m => {
      const raw = data.series[m.key].value;
      const b = behavioral(raw);
      return { ...m, raw, behav: b.curve, sells: b.sells, dd: data.series[m.key].dd };
    });
    let vMin = Infinity, vMax = -Infinity;
    for (const s of series) for (const arr of [s.raw, s.behav]) for (const v of arr) {
      if (v < vMin) vMin = v; if (v > vMax) vMax = v;
    }
    const eras = ERAS.map(e => ({
      ...e,
      i0: data.dates.findIndex(d => d >= e.from),
      i1: data.dates.findIndex(d => d >= e.to),
    })).filter(e => e.i0 > 0);
    return { n, series, lMin: Math.log(vMin * 0.93), lMax: Math.log(vMax * 1.07), eras };
  }, [data]);

  // autostart on scroll into view
  useEffect(() => {
    if (!C || startedRef.current || !boxRef.current) return;
    const obs = new IntersectionObserver(([e]) => {
      if (e.isIntersecting && !startedRef.current) { startedRef.current = true; setAct('one'); }
    }, { threshold: 0.35 });
    obs.observe(boxRef.current);
    return () => obs.disconnect();
  }, [C]);

  // animation driver
  useEffect(() => {
    if (!C || (act !== 'one' && act !== 'two')) return;
    const dur = act === 'one' ? ACT1_MS : ACT2_MS;
    const step = C.n / (dur / 16.7);
    const tick = () => {
      setCursor(c => {
        const nc = c + step;
        if (nc >= C.n - 1) {
          if (act === 'one') {
            setTimeout(() => { setCursor(0); setAct('two'); }, INTERLUDE_MS);
            setAct('interlude');
          } else {
            setAct('done');
          }
          return C.n - 1;
        }
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
  const behavMode = act === 'two' || act === 'done';
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
  const yearTicks = [];
  for (let yr = 2008; yr <= 2026; yr += 3) {
    const idx = data.dates.findIndex(d => d.startsWith(String(yr)));
    if (idx > 0) yearTicks.push([idx, yr]);
  }

  const titles = {
    idle: 'Two decades. Three crashes. $100,000.',
    one: 'Act I — the theoretical race.',
    interlude: 'But almost nobody holds through a 25% loss…',
    two: 'Act II — the same 20 years, with human behavior.',
    done: 'What you actually collect.',
  };

  const restart = () => { setCursor(0); setAct('one'); };

  return (
    <div ref={boxRef} className="bg-paper-card border border-rule p-6 sm:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
        <div>
          <div className="font-body text-[0.75rem] font-medium tracking-[0.15em] uppercase text-ink-mute">
            $100,000 · {data.span || '2007–2026'} · walk-forward backtest
          </div>
          <div className={`font-display text-[1.3rem] mt-0.5 transition-colors duration-500 ${act === 'interlude' ? 'text-claret italic' : 'text-ink'}`}
            style={{ fontVariationSettings: '"opsz" 96' }}>
            {titles[act]}
          </div>
        </div>
        {(act === 'done' || act === 'idle') && (
          <button onClick={restart} className="text-[0.8rem] px-3 py-1.5 border border-rule-dark text-ink-mute hover:text-ink transition-colors">
            {act === 'done' ? '↻ Replay' : '▶ Play'}
          </button>
        )}
      </div>

      {/* Scoreboard — fixed buckets, money ticks here (not on the chart) */}
      <div className="grid grid-cols-3 gap-px bg-rule mb-5">
        {series.map(s => {
          const arr = behavMode ? s.behav : s.raw;
          const cur = arr[ci];
          const theo = s.raw[n - 1];
          const ddNow = s.dd[ci];
          const flaring = !behavMode && act !== 'done' && ddNow < -15;
          const soldOut = behavMode && act === 'two' && s.sells.some(i => i <= ci) && cur === arr[Math.max(0, ci)] && s.sells.filter(i => i <= ci).length > 0;
          return (
            <div key={s.key} className="bg-paper p-3 sm:p-4 text-center">
              <div className="font-body text-[0.7rem] font-medium tracking-[0.12em] uppercase mb-1" style={{ color: s.color }}>
                {s.label}
              </div>
              <div className="font-mono text-[1.15rem] sm:text-[1.45rem] font-semibold tabular-nums"
                style={{ color: act === 'done' && s.key === 'rigacap' ? '#2D5F3F' : '#141210' }}>
                {fmtMoney(cur)}
              </div>
              <div className="h-5 text-[0.72rem] font-mono mt-0.5">
                {act === 'done' ? (
                  s.sells.length
                    ? <span className="text-ink-light">panic-sold {s.sells.length}× · <s>{fmtMoney(theo)}</s> theoretical</span>
                    : <span style={{ color: '#2D5F3F' }}>never panic-sold</span>
                ) : flaring ? (
                  <span style={{ color: '#8F2D3D' }}>▼ {Math.abs(ddNow).toFixed(0)}% from peak</span>
                ) : behavMode && s.sells.filter(i => i <= ci).length > 0 && act === 'two' ? (
                  <span style={{ color: '#8F2D3D' }}>sold {s.sells.filter(i => i <= ci).length}×</span>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img"
        aria-label="Animated comparison of $100,000 in RigaCap, the S&P 500, and raw momentum, 2007 to 2026, with and without panic-selling">
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
        {series.map(s => {
          const arr = behavMode ? s.behav : s.raw;
          return (
            <g key={s.key}>
              <path d={path(arr)} fill="none" stroke={s.color} strokeWidth={s.key === 'rigacap' ? 2.5 : 1.5} strokeLinejoin="round" />
              <circle cx={x(ci)} cy={y(arr[ci])} r="3.5" fill={s.color} />
              {behavMode && s.sells.filter(i => i <= ci).map(i => (
                <g key={i}>
                  <circle cx={x(i)} cy={y(arr[i])} r="4" fill="none" stroke="#8F2D3D" strokeWidth="1.5" />
                  <text x={x(i)} y={y(arr[i]) - 8} textAnchor="middle" fontSize="9.5" fill="#8F2D3D" fontFamily="IBM Plex Mono, monospace">sold</text>
                </g>
              ))}
            </g>
          );
        })}
        <line x1={x(ci)} x2={x(ci)} y1={PAD_T} y2={H - PAD_B} stroke="#8A8578" strokeWidth="0.75" strokeDasharray="3 4" opacity="0.6" />
        <text x={Math.min(x(ci), W - 36)} y={PAD_T - 4} textAnchor="middle" fontSize="13" fontWeight="600" fill="#141210" fontFamily="IBM Plex Mono, monospace">
          {data.dates[ci].slice(0, 4)}
        </text>
        {activeEra && (
          <text x={x(activeEra.i0) + 4} y={PAD_T + 16} fontSize="12" fontStyle="italic" fill="#8F2D3D" fontFamily="Fraunces, serif">
            {activeEra.label}
          </text>
        )}
      </svg>

      {act === 'done' && (
        <p className="mt-4 text-[0.95rem] text-ink leading-[1.65] max-w-[68ch]">
          Raw momentum's $2.9M assumed a robot held it through a 57% crash and four more gut-punches.
          A human who bails at −25% collected <strong className="font-medium">$348k from raw momentum, $210k from the index
          — and $473k from RigaCap</strong>, which never gave them a reason to bail.
          <em className="font-display italic text-claret"> The drawdown you can live with decides the return you actually get.</em>
        </p>
      )}

      <p className="mt-4 text-[0.8rem] text-ink-light leading-relaxed">
        Walk-forward backtest, price returns; raw momentum gross of costs. 2016+ data survivorship-free; pre-2016 carries a
        survivorship caveat (see <a href="/methodology" className="underline underline-offset-2">methodology</a>). Act II sells
        after a 25% loss from peak and re-enters at recovery to the prior peak. Backtested; not a prediction.
      </p>
    </div>
  );
}

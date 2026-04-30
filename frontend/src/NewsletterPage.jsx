import React, { useEffect, useState } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Calendar, TrendingUp, Eye, ChevronRight, Loader2 } from 'lucide-react';
import MarketMeasuredSignup from './components/MarketMeasuredSignup';
import TopNav from './components/TopNav';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const SectionLabel = ({ children }) => (
  <div className="flex items-center gap-3 mb-6">
    <span className="inline-block w-6 h-px bg-claret" />
    <span className="font-body text-[0.78rem] font-medium tracking-[0.18em] uppercase text-ink-mute">{children}</span>
  </div>
);

const Navbar = () => <TopNav />;

const REGIME_COLORS = {
  'Strong Bull': '#2D5F3F',
  'Weak Bull': '#5A7F5F',
  'Rotating Bull': '#7A8F5F',
  'Range Bound': '#8A8279',
  'Weak Bear': '#8F6D3D',
  'Panic Crash': '#8F2D3D',
  'Recovery': '#3D6F8F',
};

function formatDate(dateStr) {
  const d = new Date(dateStr + 'T12:00:00');
  return d.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
}

function formatDateShort(dateStr) {
  const d = new Date(dateStr + 'T12:00:00');
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

const SectionBreak = () => (
  <div className="flex items-center justify-center gap-2 my-14 text-rule-dark">
    <span className="flex-1 h-px bg-rule" />
    <span className="font-mono text-[0.7rem] tracking-[0.3em] text-rule-dark">···</span>
    <span className="flex-1 h-px bg-rule" />
  </div>
);

const NewsletterSection = ({ num, label, title, children }) => (
  <div className="mb-0">
    <p className="font-mono text-[0.75rem] font-medium tracking-[0.2em] text-claret uppercase mb-3">
      &sect; {num} &middot; {label}
    </p>
    {title && (
      <h2
        className="font-display text-ink mb-5 tracking-[-0.02em] leading-[1.15]"
        style={{ fontSize: 'clamp(1.5rem, 3.5vw, 2rem)', fontVariationSettings: '"opsz" 96' }}
        dangerouslySetInnerHTML={{ __html: title.replace(/<em>/g, '<em class="text-claret">') }}
      />
    )}
    {children}
  </div>
);

export function NewsletterIssuePage() {
  const { date } = useParams();
  const navigate = useNavigate();
  const [issue, setIssue] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    document.title = `Market, Measured — ${date} | RigaCap`;
    fetch(`${API_BASE}/api/public/newsletter/issue/${date}`)
      .then(r => { if (!r.ok) throw new Error('Not found'); return r.json(); })
      .then(data => { setIssue(data); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, [date]);

  if (loading) return (
    <div className="min-h-screen bg-paper font-body text-ink flex items-center justify-center">
      <Loader2 className="w-6 h-6 animate-spin text-ink-mute" />
    </div>
  );

  if (error || !issue) return (
    <div className="min-h-screen bg-paper font-body text-ink">
      <Navbar />
      <div className="max-w-[720px] mx-auto px-4 sm:px-8 py-20 text-center">
        <h1 className="font-display text-2xl text-ink mb-4" style={{ fontVariationSettings: '"opsz" 48' }}>Issue not found</h1>
        <p className="text-ink-mute mb-8">This issue may not be archived yet.</p>
        <Link to="/newsletter" className="text-claret no-underline hover:underline">Back to archive</Link>
      </div>
    </div>
  );

  const sections = issue.sections;
  const hasStructuredSections = sections && sections.length > 0;

  return (
    <div className="min-h-screen bg-paper font-body text-ink text-[17px] leading-[1.65] antialiased">
      <Navbar />

      {/* Back to archive */}
      <div className="max-w-[720px] mx-auto px-4 sm:px-8 pt-6">
        <Link to="/newsletter" className="inline-flex items-center gap-1.5 text-ink-mute hover:text-ink text-[0.85rem] no-underline transition-colors">
          <ArrowLeft size={15} />
          All issues
        </Link>
      </div>

      {/* Masthead */}
      <header className="pt-8 pb-10 sm:pt-10 sm:pb-12 text-center border-b-2 border-ink">
        <div className="max-w-[720px] mx-auto px-4 sm:px-8">
          <p className="font-body text-[0.78rem] font-medium tracking-[0.25em] uppercase text-ink-mute mb-5">
            The Weekly Letter &middot; From RigaCap
          </p>
          <h1
            className="font-display font-normal text-ink leading-none tracking-[-0.025em]"
            style={{ fontSize: 'clamp(2.5rem, 6vw, 4rem)', fontVariationSettings: '"opsz" 144' }}
          >
            The Market, <em className="text-claret italic">Measured.</em>
          </h1>
          <p className="font-display italic text-ink-mute text-[1.15rem] mt-3" style={{ fontVariationSettings: '"opsz" 48' }}>
            A weekly read of what the system is seeing, and why.
          </p>
        </div>
      </header>

      {/* Issue bar */}
      <div className="border-b border-rule">
        <div className="max-w-[720px] mx-auto px-4 sm:px-8 py-3 flex justify-between items-center font-mono text-[0.78rem] tracking-[0.1em] text-ink-light">
          <span className="font-medium text-ink">{issue.date?.toUpperCase?.() || date}</span>
          <span>~5 min read</span>
        </div>
      </div>

      {/* Article */}
      <article className="max-w-[720px] mx-auto px-4 sm:px-8 py-12 sm:py-16">
        {hasStructuredSections ? (
          <>
            {sections.map((sec, i) => (
              <div key={sec.num || i}>
                <NewsletterSection num={sec.num} label={sec.label} title={sec.title}>
                  {sec.body && (
                    <div
                      className="text-[1.05rem] leading-[1.75] text-ink [&>p]:mb-5 [&>p:last-child]:mb-0 [&_strong]:font-medium [&_em]:font-display [&_em]:italic"
                      dangerouslySetInnerHTML={{ __html: sec.body.replace(/<p /g, '<p ').replace(/<\/p>/g, '</p>') }}
                    />
                  )}
                  {sec.items && (
                    <>
                      <p className="text-[1.05rem] leading-[1.75] text-ink mb-4">Right now, the system is:</p>
                      <ul className="list-none p-0 m-0 mb-5">
                        {sec.items.map((item, j) => (
                          <li key={j} className="py-3 pl-5 border-t border-rule text-[1.02rem] leading-[1.7] relative last:border-b">
                            <span className="absolute left-0 top-3 text-claret font-display">&mdash;</span>
                            <span dangerouslySetInnerHTML={{ __html: item }} />
                          </li>
                        ))}
                      </ul>
                      <p className="text-[1.05rem] leading-[1.75] text-ink font-display italic">
                        If you're looking for a system that does all of those things, this isn't it. What you're getting instead is a system that tries to do one thing very well and is transparent about what it won't do.
                      </p>
                    </>
                  )}
                  {sec.num === '04' && (
                    <div className="border-t border-rule pt-6 mt-8">
                      <p className="text-[1.05rem] text-ink mb-4">See you next Sunday.</p>
                      <p className="font-display italic text-claret text-[1.3rem]" style={{ fontVariationSettings: '"opsz" 72' }}>&mdash; Erik</p>
                    </div>
                  )}
                </NewsletterSection>
                {i < sections.length - 1 && <SectionBreak />}
              </div>
            ))}
          </>
        ) : (
          <div
            className="bg-paper-card border border-rule overflow-hidden p-8"
            style={{ maxWidth: 640, margin: '0 auto' }}
          >
            <div dangerouslySetInnerHTML={{ __html: issue.html }} />
          </div>
        )}

        {/* Subscribe box */}
        <div className="mt-14 bg-paper-card border border-rule-dark p-8 sm:p-10 text-center">
          <h3
            className="font-display text-[1.4rem] font-medium text-ink mb-1.5 tracking-[-0.015em]"
            style={{ fontVariationSettings: '"opsz" 72' }}
          >
            The Market, Measured. <em className="text-claret italic">Delivered Sundays.</em>
          </h3>
          <p className="text-ink-mute text-[0.95rem] mb-5 max-w-[45ch] mx-auto">
            A weekly read of what the system is seeing. Free. No spam. Unsubscribe anytime.
          </p>
          <MarketMeasuredSignup source="archive_issue" />
        </div>

        {/* Product pitch */}
        <div className="border-t border-b border-rule py-6 mt-10 font-display italic text-[1.05rem] leading-[1.6] text-ink-mute" style={{ fontVariationSettings: '"opsz" 48' }}>
          RigaCap is a disciplined momentum signal service built by a former Chief Innovation Officer with 15 years of quantitative research. Walk-forward validated. $129/month with a 7-day free trial.{' '}
          <Link to="/" className="text-claret underline decoration-1 underline-offset-2">Start your trial &rarr;</Link>
        </div>
      </article>

      {/* Footer */}
      <footer className="border-t border-rule py-10 bg-paper-deep">
        <div className="max-w-[720px] mx-auto px-4 sm:px-8 text-center">
          <p className="font-display italic text-ink-mute text-[0.95rem]" style={{ fontVariationSettings: '"opsz" 24' }}>
            Three-to-four signals a month, sometimes zero. We trade when the math is clear.
          </p>
          <div className="flex items-center justify-center gap-6 mt-5 text-[0.85rem] text-ink-light">
            <Link to="/" className="no-underline hover:text-ink transition-colors">Home</Link>
            <Link to="/methodology" className="no-underline hover:text-ink transition-colors">Methodology</Link>
            <Link to="/track-record" className="no-underline hover:text-ink transition-colors">Track Record</Link>
            <Link to="/about" className="no-underline hover:text-ink transition-colors">About</Link>
          </div>
          <p className="font-mono text-[0.7rem] text-ink-light mt-5">&copy; {new Date().getFullYear()} RigaCap, LLC &middot; For information purposes only</p>
        </div>
      </footer>
    </div>
  );
}

export default function NewsletterPage() {
  const [issues, setIssues] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    document.title = 'Market, Measured — Newsletter Archive | RigaCap';
    fetch(`${API_BASE}/api/public/newsletter/archive`)
      .then(r => r.json())
      .then(data => { setIssues(data.issues || []); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const latest = issues[0];
  const archive = issues.slice(1);

  return (
    <div className="min-h-screen bg-paper font-body text-ink text-[17px] leading-[1.65] antialiased">
      <Navbar />

      {/* Masthead */}
      <header className="pt-16 pb-10 sm:pt-20 sm:pb-12 text-center border-b-2 border-ink">
        <div className="max-w-[720px] mx-auto px-4 sm:px-8">
          <p className="font-body text-[0.78rem] font-medium tracking-[0.25em] uppercase text-ink-mute mb-5">
            The Weekly Letter &middot; From RigaCap
          </p>
          <h1
            className="font-display font-normal text-ink leading-none tracking-[-0.025em]"
            style={{ fontSize: 'clamp(2.5rem, 6vw, 4rem)', fontVariationSettings: '"opsz" 144' }}
          >
            The Market, <em className="text-claret italic">Measured.</em>
          </h1>
          <p className="font-display italic text-ink-mute text-[1.15rem] mt-3" style={{ fontVariationSettings: '"opsz" 48' }}>
            A weekly read of what the system is seeing, and why.
          </p>
        </div>
      </header>

      <div className="max-w-[720px] mx-auto px-4 sm:px-8">
        {loading ? (
          <div className="py-20 flex justify-center">
            <Loader2 className="w-6 h-6 animate-spin text-ink-mute" />
          </div>
        ) : issues.length === 0 ? (
          <div className="py-20 text-center">
            <p className="font-display italic text-ink-mute text-lg" style={{ fontVariationSettings: '"opsz" 24' }}>
              The first issue is on its way. Check back Sunday.
            </p>
          </div>
        ) : (
          <>
            {/* Latest Issue */}
            {latest && (
              <div className="py-10 border-b border-rule">
                <SectionLabel>Latest Issue</SectionLabel>
                <button
                  onClick={() => navigate(`/newsletter/${latest.date}`)}
                  className="w-full text-left group"
                >
                  <h2 className="font-display text-[1.5rem] text-ink group-hover:text-claret transition-colors mb-2" style={{ fontVariationSettings: '"opsz" 48' }}>
                    {latest.subject}
                  </h2>
                  <div className="flex items-center gap-4 text-[0.85rem] text-ink-mute">
                    <span className="flex items-center gap-1.5">
                      <Calendar size={14} />
                      {formatDate(latest.date)}
                    </span>
                    {latest.regime && (
                      <span className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: REGIME_COLORS[latest.regime] || '#8A8279' }} />
                        {latest.regime}
                      </span>
                    )}
                    {latest.fresh_count > 0 && (
                      <span className="flex items-center gap-1.5">
                        <TrendingUp size={14} />
                        {latest.fresh_count} signal{latest.fresh_count !== 1 ? 's' : ''}
                      </span>
                    )}
                  </div>
                  <p className="mt-3 text-[0.95rem] text-ink-mute">
                    Read the full issue <ChevronRight size={14} className="inline relative top-[1px]" />
                  </p>
                </button>
              </div>
            )}

            {/* Archive */}
            {archive.length > 0 && (
              <div className="py-10">
                <SectionLabel>Archive</SectionLabel>
                <div className="space-y-0">
                  {archive.map(issue => (
                    <button
                      key={issue.date}
                      onClick={() => navigate(`/newsletter/${issue.date}`)}
                      className="w-full text-left flex items-center justify-between py-4 border-b border-rule group hover:bg-paper-card transition-colors -mx-3 px-3"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-3">
                          <span className="font-mono text-[0.8rem] text-ink-light w-16 shrink-0">{formatDateShort(issue.date)}</span>
                          <span className="font-display text-[1rem] text-ink group-hover:text-claret transition-colors truncate" style={{ fontVariationSettings: '"opsz" 24' }}>
                            {issue.subject}
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 ml-4 shrink-0">
                        {issue.regime && (
                          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: REGIME_COLORS[issue.regime] || '#8A8279' }} />
                        )}
                        {issue.fresh_count > 0 && (
                          <span className="font-mono text-[0.75rem] text-positive">{issue.fresh_count} sig</span>
                        )}
                        <ChevronRight size={14} className="text-ink-light group-hover:text-claret transition-colors" />
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {/* Subscribe — after the archive */}
        <div className="py-10 border-t border-rule">
          <MarketMeasuredSignup source="archive_page" />
        </div>
      </div>

      {/* Footer */}
      <footer className="border-t border-rule mt-12 py-10">
        <div className="max-w-[720px] mx-auto px-4 sm:px-8 text-center">
          <p className="font-display italic text-ink-mute text-[0.95rem]" style={{ fontVariationSettings: '"opsz" 24' }}>
            Three-to-four signals a month, sometimes zero. We trade when the math is clear.
          </p>
          <div className="flex items-center justify-center gap-6 mt-5 text-[0.85rem] text-ink-light">
            <Link to="/" className="no-underline hover:text-ink transition-colors">Home</Link>
            <Link to="/methodology" className="no-underline hover:text-ink transition-colors">Methodology</Link>
            <Link to="/track-record" className="no-underline hover:text-ink transition-colors">Track Record</Link>
            <Link to="/about" className="no-underline hover:text-ink transition-colors">About</Link>
          </div>
          <p className="font-mono text-[0.7rem] text-ink-light mt-5">&copy; {new Date().getFullYear()} RigaCap, LLC &middot; For information purposes only</p>
        </div>
      </footer>
    </div>
  );
}

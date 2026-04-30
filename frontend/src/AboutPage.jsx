import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import TopNav from './components/TopNav';

const SectionLabel = ({ children }) => (
  <div className="flex items-center gap-3 mb-6">
    <span className="inline-block w-6 h-px bg-claret" />
    <span className="font-body text-[0.78rem] font-medium tracking-[0.18em] uppercase text-ink-mute">{children}</span>
  </div>
);

const Navbar = () => <TopNav />;

export default function AboutPage() {
  useEffect(() => { document.title = 'About — RigaCap'; }, []);

  return (
    <div className="min-h-screen bg-paper font-body text-ink text-[17px] leading-[1.65] antialiased">
      <Navbar />

      {/* Article Header */}
      <header className="pt-16 pb-14 sm:pt-20 sm:pb-16 border-b border-rule">
        <div className="max-w-[720px] mx-auto px-4 sm:px-8">
          <SectionLabel>About</SectionLabel>
          <h1
            className="font-display font-normal text-ink mb-7 tracking-[-0.025em] leading-[1.05]"
            style={{ fontSize: 'clamp(2.25rem, 4.5vw, 3.6rem)', fontVariationSettings: '"opsz" 144' }}
          >
            I built RigaCap because it's the product <em className="text-claret italic">I wanted to use myself.</em>
          </h1>
          <p className="font-display italic text-ink-mute text-[1.3rem] leading-[1.55]" style={{ fontVariationSettings: '"opsz" 48' }}>
            A self-taught engineer, a former Chief Innovation Officer, and 15 years of quantitative research that finally caught up to the tools required to ship it.
          </p>

          <div className="flex items-center gap-4 mt-10 pt-6 border-t border-rule">
            <img
              src="/erikheadshot.jpg"
              alt="Erik Kins"
              className="w-12 h-12 object-cover object-top rounded-none border border-rule-dark"
            />
            <div className="text-[0.88rem] text-ink-mute">
              <strong className="block text-ink font-medium text-[0.95rem]">Erik Kins</strong>
              Founder, RigaCap
            </div>
          </div>
        </div>
      </header>

      {/* Article Body */}
      <article className="py-16 sm:py-20">
        <div className="max-w-[1080px] mx-auto px-4 sm:px-8 grid md:grid-cols-[3fr_1fr] gap-16">

          {/* Prose */}
          <div className="max-w-[62ch]">
            <p className="font-display text-[1.45rem] leading-[1.45] text-ink mb-7" style={{ fontVariationSettings: '"opsz" 48' }}>
              For 15 years, I've been running quantitative research as a parallel practice alongside a career building healthcare software. RigaCap is what happens when those two tracks finally converge: an <em className="text-claret italic">institutional-caliber signal system, built by one person,</em> priced for individuals.
            </p>

            <p className="text-[1.1rem] leading-[1.75] mb-5">
              The name is a nod to Riga, Latvia &mdash; where, in 2006, a song I wrote became the #1 record in the country. That's not a fintech credential. But it's the first piece of evidence I'd offer that the pattern behind this product &mdash; <em className="font-display italic">self-taught, focused, finishes things</em> &mdash; is real.
            </p>

            <hr className="w-16 h-px bg-rule-dark border-none my-12" />

            <h2 className="font-display text-[1.9rem] font-medium text-ink mb-5 tracking-[-0.015em] leading-[1.15]" style={{ fontVariationSettings: '"opsz" 96' }}>
              The software career.
            </h2>

            <p className="text-[1.1rem] leading-[1.75] mb-5">
              I started at a $1.5B publicly traded healthcare software company in 2003 as a senior software developer. I don't have a computer science degree &mdash; my degree from Lehigh University is in International Business and International Relations, and I've never taken a computer science course in my life. Everything I know about building software, I learned by building software. Over fifteen years there, I went from writing code to leading global engineering teams, and left as <strong className="font-medium">Chief Innovation Officer</strong> in 2018.
            </p>

            <p className="text-[1.1rem] leading-[1.75] mb-5">
              In between, I built things that operated at genuine scale:
            </p>

            <ul className="list-none my-7 space-y-0">
              {[
                <><strong className="font-medium">The first cloud-based e-prescribing platform</strong> open to any licensed US physician, part of the National ePrescribing Safety Initiative. It processed nearly 150 million prescriptions, peaking at 800,000 per week. I invented &ldquo;Preemptive DUR&rdquo; &mdash; a drug-interaction check that runs <em className="font-display italic">before</em> the prescription is written rather than after.</>,
                <><strong className="font-medium">The first bi-directional physician clinical applications</strong> on iPhone, iPad, Android, BlackBerry, and Windows. Before these, physicians couldn't meaningfully interact with their EHRs from a phone. After, they could.</>,
                <><strong className="font-medium">A healthcare API platform</strong> that scaled from 250 million to over 4 billion third-party data shares per year under my leadership, and eventually integrated with Apple Health.</>,
                <><strong className="font-medium">Ubiquity</strong>, a patent-filed cloud-based pub-sub routing system for on-premise clinical databases &mdash; the kind of infrastructure problem that doesn't have a glamorous name but underpins everything built on top of it.</>,
              ].map((item, i) => (
                <li key={i} className="py-5 pl-6 border-t border-rule relative text-[1.05rem] leading-[1.7] last:border-b">
                  <span className="absolute left-0 top-5 font-display text-claret">&mdash;</span>
                  {item}
                </li>
              ))}
            </ul>

            <p className="text-[1.1rem] leading-[1.75] mb-5">
              I led global engineering teams of up to 50 people and shipped software that millions of clinicians and patients depended on. I learned what it takes to build systems that have to be right.
            </p>

            <hr className="w-16 h-px bg-rule-dark border-none my-12" />

            <h2 className="font-display text-[1.9rem] font-medium text-ink mb-5 tracking-[-0.015em] leading-[1.15]" style={{ fontVariationSettings: '"opsz" 96' }}>
              The <em className="text-claret italic">quant practice.</em>
            </h2>

            <p className="text-[1.1rem] leading-[1.75] mb-5">
              This one started with my father &mdash; a lifelong investment hobbyist, the kind who's watched IBD cup-and-handle patterns, relative strength scores, and head-and-shoulders formations for so long that he can see them before the chart finishes drawing them. Fifteen years ago, he asked me a simple question: <em className="font-display italic">could I write something that predicts what he was already intuiting from those patterns?</em>
            </p>

            <p className="text-[1.1rem] leading-[1.75] mb-5">
              So I started. A SQL database. A subscription to closing-price data. Hundreds of theoretical stored procedures, each trying and mostly failing to pick winners. It turned out the question he'd asked was harder than either of us initially thought &mdash; and the tools to answer it well didn't yet exist.
            </p>

            <p className="text-[1.1rem] leading-[1.75] mb-5">
              Fifteen years later, they do. Cloud compute is cheap, historical data is comprehensive, modern optimization libraries make Bayesian parameter search routine rather than exotic, and &mdash; crucially &mdash; I now have fifteen years of personal pattern memory across multiple market cycles to inform which ideas are worth testing and which aren't. The Ensemble strategy that powers RigaCap is what came out of that convergence: <strong className="font-medium">decades of discretionary pattern recognition, made systematic.</strong>
            </p>

            <blockquote
              className="font-display italic text-claret text-[1.7rem] leading-[1.35] border-l-[3px] border-claret py-4 pl-7 my-10 max-w-[55ch]"
              style={{ fontVariationSettings: '"opsz" 96' }}
            >
              Honestly, I had to wait until 2026 to build this. The question was right; the answer was just a decade and a half of tooling away.
            </blockquote>

            <hr className="w-16 h-px bg-rule-dark border-none my-12" />

            <h2 className="font-display text-[1.9rem] font-medium text-ink mb-5 tracking-[-0.015em] leading-[1.15]" style={{ fontVariationSettings: '"opsz" 96' }}>
              Why <em className="text-claret italic">solo.</em>
            </h2>

            <p className="text-[1.1rem] leading-[1.75] mb-5">
              After the CIO role, I did a stint as VP of Innovation at a smaller company, consulted independently, and have been running an executive-producer role in film production since 2022. What I've learned across all of it: the things I'm best at building are the things I can build with <em className="font-display italic">focus</em>, not with <em className="font-display italic">headcount</em>. RigaCap doesn't need a team. It needs to be right.
            </p>

            <p className="text-[1.1rem] leading-[1.75] mb-5">
              So there's no team, no outside capital, no growth-at-all-costs mandate. Just me, the system, and a commitment to publishing what I do honestly &mdash; including the assumptions, the friction-adjusted numbers, and the methodology behind every signal.
            </p>

            <p className="text-[1.1rem] leading-[1.75]">
              <em className="font-display italic">If that's the kind of product you want to subscribe to, you're in the right place.</em>
            </p>
          </div>

          {/* Sidebar */}
          <aside className="md:sticky md:top-8 self-start">
            <div className="w-full aspect-[4/5] border border-rule overflow-hidden mb-6">
              <img
                src="/erikheadshot.jpg"
                alt="Erik Kins"
                className="w-full h-full object-cover object-top"
              />
            </div>

            <dl className="text-[0.88rem] leading-[1.6]">
              {[
                ['Name', 'Erik Kins'],
                ['Based in', 'Los Angeles, California'],
                ['Education', 'BA, International Business & International Relations, Lehigh University'],
                ['Previously', 'Chief Innovation Officer, $1.5B publicly traded healthcare software co.'],
                ['Patent', 'Ubiquity — cloud-based pub-sub routing for clinical databases'],
                ['One weird fact', 'Had the #1 song in Latvia in 2006.'],
              ].map(([label, value], i) => (
                <React.Fragment key={label}>
                  <dt className={`font-body text-[0.7rem] font-medium tracking-[0.15em] uppercase text-ink-mute mb-1 ${i > 0 ? 'mt-4' : ''}`}>{label}</dt>
                  <dd className="text-ink ml-0 pb-3 border-b border-rule">{value}</dd>
                </React.Fragment>
              ))}
            </dl>

            <div className="mt-8 pt-6 border-t border-rule space-y-2.5">
              <a href="mailto:erik@rigacap.com" className="block font-display italic text-claret no-underline text-[1rem]" style={{ fontVariationSettings: '"opsz" 48' }}>
                → erik@rigacap.com
              </a>
              <Link to="/#newsletter" className="block font-display italic text-claret no-underline text-[1rem]" style={{ fontVariationSettings: '"opsz" 48' }}>
                → The weekly letter
              </Link>
            </div>
          </aside>
        </div>
      </article>

      {/* Closing CTA */}
      <section className="bg-paper-deep py-20 border-t border-rule text-center">
        <div className="max-w-[1120px] mx-auto px-4 sm:px-8">
          <h2 className="font-display font-normal text-ink mb-6 tracking-[-0.02em]" style={{ fontSize: 'clamp(1.8rem, 3.5vw, 2.75rem)', fontVariationSettings: '"opsz" 96' }}>
            Read the system, then <em className="text-claret italic">decide for yourself.</em>
          </h2>
          <p className="text-ink-mute text-[1.1rem] max-w-[50ch] mx-auto mb-10">
            The methodology is public. The assumptions are disclosed. The free weekly letter tells you what the system is seeing. Everything you need to evaluate this before paying a dollar is available.
          </p>
          <Link
            to="/methodology"
            className="inline-block px-7 py-4 bg-ink text-paper text-[0.95rem] font-medium rounded-[2px] no-underline hover:bg-claret transition-colors"
          >
            See the methodology
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-paper-deep border-t border-rule pt-16 pb-8">
        <div className="max-w-[1120px] mx-auto px-4 sm:px-8">
          <div className="grid sm:grid-cols-2 lg:grid-cols-[2fr_1fr_1fr_1fr] gap-12 pb-12 border-b border-rule">
            <div>
              <Link to="/" className="font-display text-[1.4rem] font-semibold text-ink no-underline" style={{ fontVariationSettings: '"opsz" 144' }}>
                RigaCap<span className="text-claret">.</span>
              </Link>
              <p className="mt-4 text-[0.9rem] text-ink-mute leading-relaxed max-w-[32ch]">
                Ensemble trading signals. The market, measured. Built by one quant researcher, shipping honestly.
              </p>
            </div>
            {[
              ['Product', [['Methodology', '/methodology'], ['Track Record', '/track-record'], ['Pricing', '/#pricing']]],
              ['Company', [['About', '/about'], ['Newsletter', '/#newsletter'], ['Blog', '/blog'], ['Contact', '/contact']]],
              ['Legal', [['Terms', '/terms'], ['Privacy', '/privacy'], ['Disclaimer', '/disclaimer']]],
            ].map(([heading, links]) => (
              <div key={heading}>
                <h4 className="font-body text-[0.75rem] font-medium tracking-[0.15em] uppercase text-ink mb-4">{heading}</h4>
                <ul className="space-y-2">
                  {links.map(([label, href]) => (
                    <li key={label}><Link to={href} className="text-ink-mute text-[0.92rem] no-underline hover:text-ink transition-colors">{label}</Link></li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
          <div className="pt-8 flex flex-col sm:flex-row justify-between items-start gap-8">
            <p className="text-[0.78rem] text-ink-light leading-relaxed max-w-[70ch]">
              For information purposes only. Not a solicitation to invest, purchase, or sell securities in which RigaCap has an interest. RigaCap, LLC is not a registered investment advisor. Past performance does not guarantee future results.
            </p>
            <p className="text-[0.78rem] text-ink-light shrink-0">&copy; 2026 RigaCap, LLC</p>
          </div>
        </div>
      </footer>
    </div>
  );
}

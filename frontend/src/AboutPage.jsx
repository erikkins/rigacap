import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';

const SectionLabel = ({ children }) => (
  <div className="flex items-center gap-3 mb-6">
    <span className="inline-block w-6 h-px bg-claret" />
    <span className="font-body text-[0.78rem] font-medium tracking-[0.18em] uppercase text-ink-mute">{children}</span>
  </div>
);

const Navbar = () => (
  <nav className="sticky top-0 z-50 bg-paper/95 backdrop-blur-sm border-b border-rule">
    <div className="max-w-[1120px] mx-auto px-4 sm:px-8 py-5 flex items-center justify-between">
      <Link to="/" className="flex items-center gap-2 no-underline">
        <svg className="w-7 h-7 shrink-0 relative top-[2px]" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 1024"><g transform="matrix(5.27 0 0 5.27 640 511)"><g><g transform="matrix(0.448 0 0 0.448 -22.4 -28.8)"><path fill="#7A2430" transform="translate(-300,-286)" d="M215.49 348.13C215.49 341.43 220.55 335.98 227.05 335.22L241.64 278.36C238.32 275.99 236.13 272.12 236.13 267.73C236.13 260.51 241.98 254.66 249.2 254.66C255.89 254.66 261.34 259.71 262.11 266.19L309.18 278.16C311.55 274.82 315.42 272.63 319.83 272.63C324 272.63 327.67 274.62 330.06 277.66L391.39 258.85C391.87 252.06 397.46 246.69 404.37 246.69C405.09 246.69 405.78 246.79 406.47 246.91L420.4 223.13C395.44 205.2 364.84 194.62 331.76 194.62C247.75 194.62 179.66 262.72 179.66 346.72C179.66 357.06 180.71 367.15 182.69 376.91L216.05 351.72C215.72 350.57 215.49 349.38 215.49 348.13z"/></g><g transform="matrix(0.448 0 0 0.448 -11.1 -9)"><path fill="#7A2430" transform="translate(-325,-330)" d="M427.89 228.86L414.54 251.65C416.32 253.88 417.43 256.68 417.43 259.76C417.43 266.98 411.58 272.83 404.37 272.83C400.19 272.83 396.52 270.84 394.13 267.79L332.8 286.61C332.33 293.39 326.73 298.76 319.83 298.76C313.14 298.76 307.69 293.72 306.92 287.24L259.84 275.26C257.76 278.21 254.48 280.2 250.71 280.64L236.12 337.5C239.44 339.87 241.63 343.74 241.63 348.13C241.63 355.35 235.78 361.2 228.56 361.2C226.02 361.2 223.68 360.45 221.67 359.19L185.04 386.86C189.39 402.76 196.25 417.63 205.17 431L343.51 312.12L408.04 312.12L465.59 274.41C456.09 256.86 443.23 241.4 427.89 228.86z"/></g><g transform="matrix(0.448 0 0 0.448 73.8 -37.1)"><polygon fill="#7A2430" points="-45.31,-14.33 45.31,-39.44 -12.75,39.44 -17.06,3.28"/></g><g transform="matrix(0.448 0 0 0.448 -48.2 25.7)"><path fill="#141210" transform="translate(-242,-407)" d="M297.69 513.38C291.85 512.18 286.13 510.68 280.53 508.91L280.53 405.3L233.16 446.01L233.16 485.18C189.93 454.31 161.67 403.77 161.67 346.72C161.67 321.48 167.23 297.53 177.14 275.97L153.41 275.97C144.69 297.88 139.84 321.74 139.84 346.72C139.84 452.54 225.93 538.63 331.76 538.63C336.23 538.63 340.66 538.42 345.06 538.12L345.06 349.85L297.69 390.55L297.69 513.38z"/></g><g transform="matrix(0.448 0 0 0.448 41.6 31.4)"><path fill="#141210" transform="translate(-443,-420)" d="M523.16 333.38L501.27 333.38C501.62 337.79 501.85 342.23 501.85 346.72C501.85 381 491.63 412.92 474.11 439.65L474.11 304.24L426.75 335.28L426.75 487.65C421.24 491.37 415.52 494.78 409.58 497.85L409.58 341.74L362.22 341.74L362.22 536.19C453.61 521.55 523.67 442.17 523.67 346.72C523.67 342.23 523.46 337.79 523.16 333.38z"/></g><g transform="matrix(0.448 0 0 0.448 -11.8 -60.8)"><path fill="#141210" transform="translate(-324,-214)" d="M331.75 169.32C390.45 169.32 442.58 197.98 474.89 242.04L483.06 239.78C449.46 192.37 394.16 161.37 331.75 161.37C258.06 161.37 194.28 204.6 164.43 267.02L173.29 267.02C202.53 209.12 262.58 169.32 331.75 169.32z"/></g></g></g></svg>
        <span className="font-display text-2xl font-semibold text-ink tracking-tight" style={{ fontVariationSettings: '"opsz" 144' }}>RigaCap<span className="text-claret">.</span></span>
      </Link>
      <div className="flex items-center gap-7">
        <Link to="/methodology" className="hidden sm:inline text-[0.9rem] text-ink-mute no-underline hover:text-ink transition-colors">Methodology</Link>
        <Link to="/track-record" className="hidden sm:inline text-[0.9rem] text-ink-mute no-underline hover:text-ink transition-colors">Track Record</Link>
        <Link to="/newsletter" className="hidden sm:inline text-[0.9rem] text-ink-mute no-underline hover:text-ink transition-colors">Newsletter</Link>
        <a href="/#pricing" className="hidden sm:inline text-[0.9rem] text-ink-mute no-underline hover:text-ink transition-colors">Pricing</a>
        <Link to="/" className="bg-ink text-paper px-4 py-2.5 text-[0.9rem] font-medium rounded-[2px] hover:bg-claret transition-colors no-underline">Start Trial</Link>
      </div>
    </div>
  </nav>
);

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
              Trading involves risk. Past performance is not indicative of future results. RigaCap provides algorithmic signals for educational purposes only and is not a registered investment advisor.
            </p>
            <p className="text-[0.78rem] text-ink-light shrink-0">&copy; 2026 RigaCap, LLC</p>
          </div>
        </div>
      </footer>
    </div>
  );
}

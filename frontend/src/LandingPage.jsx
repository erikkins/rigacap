import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  TrendingUp, Zap, Shield, BarChart3, Bell, DollarSign,
  CheckCircle, ArrowRight, ChevronDown, ChevronUp, Star, Users, Target
} from 'lucide-react';
import { useAuth } from './contexts/AuthContext';
import LoginModal from './components/LoginModal';
import TrackRecordChart from './components/TrackRecordChart';
import MarketMeasuredSignup from './components/MarketMeasuredSignup';

// ============================================================================
// Landing Page Components
// ============================================================================

const HeroSection = ({ onGetStarted }) => (
  <section className="relative overflow-hidden bg-gradient-to-br from-blue-600 via-indigo-600 to-purple-700 text-white">
    {/* Animated background elements */}
    <div className="absolute inset-0 overflow-hidden">
      <div className="absolute -top-40 -right-40 w-80 h-80 bg-white/10 rounded-full blur-3xl"></div>
      <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-purple-500/20 rounded-full blur-3xl"></div>
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-blue-400/10 rounded-full blur-3xl"></div>
      {/* Floating chart lines */}
      <svg className="absolute inset-0 w-full h-full opacity-10" viewBox="0 0 1200 600">
        <path d="M0,400 Q200,350 400,380 T800,300 T1200,350" fill="none" stroke="white" strokeWidth="2"/>
        <path d="M0,450 Q300,400 600,420 T1200,380" fill="none" stroke="white" strokeWidth="1.5"/>
      </svg>
    </div>

    <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24 lg:py-32">
      <div className="text-center">
        {/* Badge */}
        <div className="inline-flex items-center gap-2 px-4 py-2 bg-white/10 backdrop-blur-sm rounded-full text-sm font-medium mb-8">
          <Zap className="w-4 h-4 text-yellow-300" />
          <span>AI-Powered Ensemble Strategy</span>
          <span className="px-2 py-0.5 bg-emerald-500 rounded-full text-xs">Timing + Momentum + Risk</span>
        </div>

        {/* Main headline */}
        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight mb-6">
          Hedge Fund Returns.
          <span className="block bg-gradient-to-r from-yellow-200 via-yellow-300 to-orange-300 bg-clip-text text-transparent pb-2">
            $39/month.
          </span>
        </h1>

        {/* Subheadline */}
        <p className="max-w-2xl mx-auto text-lg sm:text-xl text-blue-100 mb-3">
          Stop trading on emotions. Start trading on math.
        </p>
        <p className="text-sm text-blue-200/70 mb-8">+384% over 5 years. ~35% annualized. Walk-forward validated.<br />We scan 4,000 stocks daily and only speak up when the math says go.</p>

        {/* CTA Buttons */}
        <div className="flex flex-col items-center gap-4 mb-12">
          <button
            onClick={onGetStarted}
            className="group flex items-center gap-2 px-8 py-4 bg-white text-indigo-600 font-semibold rounded-xl shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 transition-all"
          >
            Start Free Trial
            <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
          </button>
          <div className="flex flex-col sm:flex-row gap-2 sm:gap-6 items-center">
            <a
              href="/track-record"
              className="flex items-center gap-2 px-4 py-2 text-white/90 font-medium hover:text-white transition-colors"
            >
              View 5-Year Track Record
              <ArrowRight className="w-4 h-4" />
            </a>
            <a
              href="/market-regime"
              className="flex items-center gap-2 px-4 py-2 text-white/90 font-medium hover:text-white transition-colors"
            >
              Free Market Intelligence
              <ArrowRight className="w-4 h-4" />
            </a>
          </div>
        </div>

        {/* Social proof */}
        <div className="flex flex-wrap justify-center items-center gap-8 text-sm text-blue-200">
          <div className="flex items-center gap-2">
            <Star className="w-5 h-5 text-yellow-300" />
            <span>Built on <strong className="text-white">15 years</strong> of personal quant research</span>
          </div>
          <div className="flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-emerald-300" />
            <span><strong className="text-white">3-Factor</strong> Ensemble Approach</span>
          </div>
        </div>
      </div>
    </div>

    {/* Wave divider */}
    <div className="absolute bottom-0 left-0 right-0">
      <svg viewBox="0 0 1440 120" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M0,64 C480,150 960,-20 1440,64 L1440,120 L0,120 Z" fill="white"/>
      </svg>
    </div>
  </section>
);

const FeatureCard = ({ icon: Icon, title, description, color }) => (
  <div className="group relative bg-white rounded-2xl p-8 shadow-lg hover:shadow-xl transition-all border border-gray-100">
    <div className={`inline-flex items-center justify-center w-14 h-14 rounded-xl ${color} mb-6`}>
      <Icon className="w-7 h-7 text-white" />
    </div>
    <h3 className="text-xl font-semibold text-gray-900 mb-3">{title}</h3>
    <p className="text-gray-600 leading-relaxed">{description}</p>
  </div>
);

const FeaturesSection = () => (
  <section className="py-20 bg-white">
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div className="text-center mb-16">
        <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-4">
          The 3-Factor Ensemble Advantage
        </h2>
        <p className="text-lg text-gray-600 max-w-2xl mx-auto">
          Our Ensemble system combines timing, momentum quality, and risk management into one
          institutional-grade platform anyone can use.
        </p>
      </div>

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
        <FeatureCard
          icon={Zap}
          title="Timing Signals"
          description="Precision entry signals that detect breakouts early. The first factor in our Ensemble approach ensures you buy at the right moment."
          color="bg-gradient-to-br from-yellow-400 to-orange-500"
        />
        <FeatureCard
          icon={TrendingUp}
          title="Momentum Quality"
          description="Only the top-ranked momentum stocks pass our filter. The second factor ensures you're buying the strongest names in the market."
          color="bg-gradient-to-br from-blue-500 to-indigo-600"
        />
        <FeatureCard
          icon={Shield}
          title="Adaptive Risk Management"
          description="Trailing stops and market regime detection protect your capital. The third factor adapts to bull, bear, and everything in between."
          color="bg-gradient-to-br from-purple-500 to-pink-500"
        />
        <FeatureCard
          icon={Bell}
          title="Daily Email Digest"
          description="Receive a beautiful summary of top Ensemble signals every evening, right to your inbox."
          color="bg-gradient-to-br from-emerald-500 to-teal-600"
        />
        <FeatureCard
          icon={Target}
          title="7 Market Regimes"
          description="Our AI detects 7 distinct market regimes — from Strong Bull to Panic/Crash — and adjusts signal parameters accordingly."
          color="bg-gradient-to-br from-red-500 to-rose-600"
        />
        <FeatureCard
          icon={DollarSign}
          title="Position Sizing"
          description="Automatic position size calculations based on your portfolio, risk tolerance, and current market regime."
          color="bg-gradient-to-br from-green-500 to-emerald-600"
        />
      </div>
    </div>
  </section>
);

const HowItWorksSection = () => (
  <section id="how-it-works" className="py-20 bg-gradient-to-b from-gray-50 to-white">
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div className="text-center mb-16">
        <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-4">
          How RigaCap Works
        </h2>
        <p className="text-lg text-gray-600 max-w-2xl mx-auto">
          From signal to execution in 4 simple steps
        </p>
      </div>

      <div className="grid md:grid-cols-4 gap-8">
        {[
          { step: 1, title: 'Scan', desc: 'Our algorithms analyze 4,000+ stocks daily, ranking by momentum, quality, and market conditions' },
          { step: 2, title: 'Signal', desc: 'When criteria align, you get actionable alerts with entry, stop, and target levels' },
          { step: 3, title: 'Buy', desc: 'Execute through your broker with confidence — every signal includes entry, stop, and target levels' },
          { step: 4, title: 'Profit', desc: 'Trailing stops protect gains while letting winners run' },
        ].map(({ step, title, desc }) => (
          <div key={step} className="relative text-center">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-indigo-600 text-white text-2xl font-bold mb-4">
              {step}
            </div>
            {step < 4 && (
              <div className="hidden md:block absolute top-8 left-[calc(50%+2rem)] right-[-50%] h-0.5 bg-indigo-200"></div>
            )}
            <h3 className="text-xl font-semibold text-gray-900 mb-2">{title}</h3>
            <p className="text-gray-600">{desc}</p>
          </div>
        ))}
      </div>
    </div>
  </section>
);

const StatsSection = () => (
  <section className="py-16 bg-indigo-600">
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-8 text-center text-white">
        {[
          { value: '~35%', label: 'Annualized Return' },
          { value: '+384%', label: '5-Year Return' },
          { value: '30%', label: 'Max Drawdown' },
          { value: '$48,400', label: 'From $10k (5yr)' },
          { value: 'Flat', label: '2022 (S&P: -20%)' },
          { value: '1.19', label: 'Sharpe Ratio' },
        ].map(({ value, label }) => (
          <div key={label}>
            <div className="text-4xl lg:text-5xl font-bold mb-2">{value}</div>
            <div className="text-indigo-200">{label}</div>
          </div>
        ))}
      </div>
      <p className="text-indigo-200 text-sm mt-6 text-center max-w-2xl mx-auto">
        Walk-forward simulation results — year-by-year testing with no hindsight bias.
        <br />Our Ensemble approach adapts through every market regime, from bull runs to bear markets.
      </p>

      {/* Compact equity curve */}
      <div className="mt-8 max-w-3xl mx-auto bg-white/5 backdrop-blur-sm rounded-xl p-4">
        <TrackRecordChart compact />
        <div className="text-center mt-3">
          <Link to="/track-record" className="text-indigo-200 hover:text-white text-xs underline underline-offset-2 transition-colors">
            View full interactive track record →
          </Link>
        </div>
      </div>
    </div>
  </section>
);

const PerformanceHighlightsSection = () => {
  return (
    <section className="py-20 bg-gradient-to-b from-white to-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-4">
            Built for Every Market Condition
          </h2>
          <p className="text-lg text-gray-600 max-w-2xl mx-auto">
            Walk-forward tested across bull markets, bear markets, and everything in between.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
          <div className="bg-white rounded-2xl p-8 shadow-lg border border-gray-100 text-center">
            <div className="text-4xl font-bold text-emerald-600 mb-2">+384%</div>
            <div className="text-sm font-medium text-gray-500 mb-1">5-Year Total Return</div>
            <div className="text-xs text-gray-400">~35% annualized</div>
            <div className="text-xs text-gray-400 mt-1">S&P 500: +84% over same period</div>
          </div>
          <div className="relative bg-white rounded-2xl p-8 shadow-lg border border-emerald-100 text-center">
            <div className="text-4xl font-bold text-emerald-600 mb-2">Flat</div>
            <div className="text-sm font-medium text-gray-500 mb-1">In 2022</div>
            <div className="text-xs text-gray-400">Preserved capital while S&P fell 20%</div>
            <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-amber-500 text-white text-[10px] font-bold px-2 py-0.5 rounded-full whitespace-nowrap hidden sm:block">Capital Protection</div>
          </div>
          <div className="bg-white rounded-2xl p-8 shadow-lg border border-gray-100 text-center">
            <div className="text-4xl font-bold text-amber-600 mb-2">30%</div>
            <div className="text-sm font-medium text-gray-500 mb-1">Max Drawdown</div>
            <div className="text-xs text-gray-400">Peak to trough, worst case</div>
            <div className="text-xs text-gray-400 mt-1">Controlled by trailing stops + regime detection</div>
          </div>
        </div>

        <p className="text-gray-400 text-xs mt-8 text-center max-w-2xl mx-auto">
          Walk-forward simulation using the Ensemble strategy with biweekly rebalancing.
          Tested across multiple start dates. Past performance does not guarantee future results.
        </p>
      </div>
    </section>
  );
};

const PricingSection = ({ onGetStarted }) => {
  const features = [
    'Unlimited real-time signals',
    'Daily email digest',
    'Stop-loss & profit targets',
    'Portfolio tracking',
    'Performance analytics',
    'Mobile-friendly dashboard',
    '4,000+ stocks scanned daily',
    'Sector & company insights',
  ];

  return (
    <section id="pricing" className="py-20 bg-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-4">
            Simple, Transparent Pricing
          </h2>
          <p className="text-lg text-gray-600 max-w-2xl mx-auto">
            Choose monthly flexibility or save with annual billing. Cancel anytime.
          </p>
        </div>

        <div className="max-w-4xl mx-auto grid md:grid-cols-2 gap-8">
          {/* Monthly Plan */}
          <div className="relative bg-white rounded-3xl shadow-xl border border-gray-200 overflow-hidden">
            <div className="p-8">
              <h3 className="text-2xl font-bold text-gray-900 mb-2">Monthly</h3>
              <p className="text-gray-600 mb-6">Pay as you go</p>

              <div className="flex items-baseline gap-2 mb-8">
                <span className="text-5xl font-bold text-gray-900">$39</span>
                <span className="text-gray-500">/month</span>
              </div>

              <ul className="space-y-3 mb-8">
                {features.map((feature) => (
                  <li key={feature} className="flex items-center gap-3">
                    <CheckCircle className="w-5 h-5 text-emerald-500 flex-shrink-0" />
                    <span className="text-gray-700 text-sm">{feature}</span>
                  </li>
                ))}
              </ul>

              <button
                onClick={() => onGetStarted('monthly')}
                className="w-full py-4 bg-gray-100 text-gray-900 font-semibold rounded-xl hover:bg-gray-200 transition-colors"
              >
                Start 7-Day Free Trial
              </button>
              <p className="text-center text-sm text-gray-500 mt-4">
                Credit card required · Cancel anytime
              </p>
            </div>
          </div>

          {/* Annual Plan */}
          <div className="relative bg-white rounded-3xl shadow-2xl border-2 border-indigo-500 overflow-hidden">
            {/* Best Value Badge */}
            <div className="absolute top-0 right-0 bg-indigo-500 text-white px-4 py-1 text-sm font-semibold rounded-bl-xl">
              BEST VALUE
            </div>
            <div className="p-8">
              <h3 className="text-2xl font-bold text-gray-900 mb-2">Annual</h3>
              <p className="text-gray-600 mb-6">Save with yearly billing</p>

              <div className="flex items-baseline gap-2 mb-2">
                <span className="text-5xl font-bold text-gray-900">$349</span>
                <span className="text-gray-500">/year</span>
              </div>
              <p className="text-emerald-600 font-medium mb-6">
                Save $119 — 3 months free!
              </p>

              <ul className="space-y-3 mb-8">
                {features.map((feature) => (
                  <li key={feature} className="flex items-center gap-3">
                    <CheckCircle className="w-5 h-5 text-emerald-500 flex-shrink-0" />
                    <span className="text-gray-700 text-sm">{feature}</span>
                  </li>
                ))}
              </ul>

              <button
                onClick={() => onGetStarted('annual')}
                className="w-full py-4 bg-indigo-600 text-white font-semibold rounded-xl hover:bg-indigo-700 transition-colors"
              >
                Start 7-Day Free Trial
              </button>
              <p className="text-center text-sm text-gray-500 mt-4">
                Credit card required · Cancel anytime
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

// REMOVED: Fake testimonials — SEC marketing compliance risk.
// Uncomment and replace with real testimonials when available.
// const TestimonialCard = ({ quote, author, role, avatar }) => ( ... );
// const TestimonialsSection = () => ( ... );

const FAQItem = ({ question, answer }) => {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b border-gray-200">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between py-6 text-left"
      >
        <span className="text-lg font-medium text-gray-900">{question}</span>
        {open ? (
          <ChevronUp className="w-5 h-5 text-gray-500" />
        ) : (
          <ChevronDown className="w-5 h-5 text-gray-500" />
        )}
      </button>
      {open && (
        <div className="pb-6 text-gray-600 leading-relaxed">
          {answer}
        </div>
      )}
    </div>
  );
};

const FAQSection = () => (
  <section className="py-20 bg-white">
    <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
      <div className="text-center mb-16">
        <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-4">
          Frequently Asked Questions
        </h2>
      </div>

      <div className="divide-y divide-gray-200">
        <FAQItem
          question="How does RigaCap generate signals?"
          answer="Our Ensemble strategy combines three proven factors: (1) Timing — detecting breakouts early, (2) Momentum Quality — only top-ranked stocks pass the filter, and (3) Adaptive Risk Management — trailing stops and 7-regime market detection adjust parameters automatically. When conditions are unfavorable, we recommend staying in cash. When opportunity strikes, all three factors must align for a signal."
        />
        <FAQItem
          question="How many signals do you generate per day?"
          answer="On average, we generate 3-4 high-conviction signals per month from a universe of 4,000+ stocks. When market conditions aren't right, the system stays quiet — that discipline is a big part of why it beats the S&P 500."
        />
        <FAQItem
          question="What's your track record?"
          answer={<>+384% over 5 years (~35% annualized) with a 1.19 Sharpe ratio — validated through walk-forward simulation with no hindsight bias. In 2022, while the S&amp;P fell 20%, our system preserved capital. See our <a href="/track-record" className="text-indigo-400 hover:text-indigo-300 underline">full track record</a>.</>}
        />
        <FAQItem
          question="Has the system ever had a down year?"
          answer="No losing year over the full 5-year walk-forward. The closest was 2022 at -0.4% (essentially flat) while the S&P fell 20%. In 2024, the system returned +1.2% during a year dominated by a handful of mega-cap tech stocks — positive, but below the S&P. Our system is built for broad momentum, not concentrated bets on the Magnificent 7. The tradeoff: we keep max drawdown around 30% with consistent positive years across different market conditions."
        />
        <FAQItem
          question="Can I cancel anytime?"
          answer="Absolutely! There are no contracts or commitments. You can cancel your subscription anytime from your account settings, and you'll retain access until the end of your billing period."
        />
        <FAQItem
          question="Do I need a brokerage account?"
          answer="Yes. RigaCap identifies what to buy and when — you execute trades through your own broker (Schwab, Fidelity, Interactive Brokers, etc.). We don't hold funds or place orders on your behalf."
        />
        <FAQItem
          question="If the system works this well, why sell signals instead of running a fund?"
          answer="Great question. Building a fund requires regulatory infrastructure, institutional capital, and a 2+ year track record — we're building that now. In the meantime, signals let us prove the system in live markets with real subscribers while we bootstrap. You get access to the same engine we'll eventually deploy with our own capital."
        />
        <FAQItem
          question="Do you provide financial advice?"
          answer="No, RigaCap provides algorithmic signals and educational information only. We are not financial advisors. Always do your own research and consider consulting a licensed professional before making investment decisions."
        />
      </div>
    </div>
  </section>
);

const CTASection = ({ onGetStarted }) => (
  <section className="py-20 bg-gradient-to-br from-indigo-600 to-purple-700 text-white">
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
      <h2 className="text-3xl sm:text-4xl font-bold mb-6">
        Ready to Start Winning?
      </h2>
      <p className="text-xl text-indigo-100 mb-10 max-w-2xl mx-auto">
        Join thousands of traders using AI-powered signals to find winning opportunities.
        Your first week is free — credit card required to start trial.
      </p>
      <button
        onClick={onGetStarted}
        className="group inline-flex items-center gap-2 px-10 py-5 bg-white text-indigo-600 font-bold text-lg rounded-xl shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 transition-all"
      >
        Start Your Free Trial
        <ArrowRight className="w-6 h-6 group-hover:translate-x-1 transition-transform" />
      </button>
    </div>
  </section>
);

const Footer = () => (
  <footer className="bg-gray-900 text-gray-400 py-12">
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div className="flex flex-col md:flex-row justify-between items-center gap-6">
        <div className="flex items-center gap-2">
          <RigaCapLogo size={32} />
          <span className="text-xl font-bold text-white">RigaCap</span>
        </div>
        <div className="flex gap-8 text-sm">
          <a href="/blog" className="hover:text-white transition-colors">Blog</a>
          <a href="/terms" className="hover:text-white transition-colors">Terms</a>
          <a href="/privacy" className="hover:text-white transition-colors">Privacy</a>
          <a href="/contact" className="hover:text-white transition-colors">Contact</a>
        </div>
        <div className="text-sm">
          &copy; {new Date().getFullYear()} RigaCap, LLC. All rights reserved.
        </div>
      </div>
      <div className="mt-8 pt-8 border-t border-gray-800 text-center text-sm">
        <p>
          Trading involves risk. Past performance does not guarantee future results.
          RigaCap provides algorithmic signals for educational purposes only and is not a registered investment advisor.
        </p>
      </div>
    </div>
  </footer>
);

const RigaCapLogo = ({ size = 40, className = '' }) => (
  <img src="/icon-halo.svg" alt="RigaCap" width={size} height={size} className={className} />
);

const Navbar = ({ onGetStarted }) => (
  <nav className="absolute top-0 left-0 right-0 z-50">
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <RigaCapLogo size={36} />
          <span className="text-xl font-bold text-white">RigaCap</span>
        </div>
        <div className="hidden md:flex items-center gap-8 text-white/80">
          <a href="#how-it-works" className="hover:text-white transition-colors">How It Works</a>
          <a href="/market-regime" className="hover:text-white transition-colors">Free Market Intel</a>
          <a href="#pricing" className="hover:text-white transition-colors">Pricing</a>
          <button
            onClick={onGetStarted}
            className="px-5 py-2 bg-white/10 backdrop-blur-sm rounded-lg hover:bg-white/20 transition-colors"
          >
            Sign In
          </button>
        </div>
      </div>
    </div>
  </nav>
);

// ============================================================================
// Main Landing Page Component
// ============================================================================

// Helper to check if user has visited before (cookie-based)
const hasVisitedBefore = () => {
  return document.cookie.includes('rigacap_visited=true');
};

const setVisitedCookie = () => {
  // Set cookie for 1 year
  const expires = new Date();
  expires.setFullYear(expires.getFullYear() + 1);
  document.cookie = `rigacap_visited=true; expires=${expires.toUTCString()}; path=/; SameSite=Lax`;
};

export default function LandingPage() {
  const navigate = useNavigate();
  const { isAuthenticated, loading } = useAuth();
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState('monthly');
  const [isReturningVisitor, setIsReturningVisitor] = useState(false);

  // Capture referral code from URL on mount
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const ref = params.get('ref');
    if (ref) {
      localStorage.setItem('rigacap_referral_code', ref.toUpperCase().trim());
      // Clean URL
      const url = new URL(window.location);
      url.searchParams.delete('ref');
      window.history.replaceState({}, '', url.pathname + url.search);
    }
  }, []);

  // Check if returning visitor on mount
  useEffect(() => {
    setIsReturningVisitor(hasVisitedBefore());
    setVisitedCookie(); // Mark as visited
  }, []);

  // Redirect if already authenticated (after loading is complete)
  useEffect(() => {
    if (!loading && isAuthenticated) {
      navigate('/app', { replace: true });
    }
  }, [isAuthenticated, loading, navigate]);

  const handleGetStarted = (plan = 'monthly') => {
    if (isAuthenticated) {
      navigate('/app', { replace: true });
    } else {
      setSelectedPlan(plan);
      setShowLoginModal(true);
    }
  };

  const handleLoginSuccess = () => {
    // Close modal first
    setShowLoginModal(false);
    // Navigate immediately - auth state is already updated in context
    navigate('/app', { replace: true });
  };

  return (
    <div className="min-h-screen bg-white">
      <Navbar onGetStarted={handleGetStarted} />
      <HeroSection onGetStarted={handleGetStarted} />
      <FeaturesSection />
      <HowItWorksSection />
      <StatsSection />
      <PerformanceHighlightsSection />
      <PricingSection onGetStarted={handleGetStarted} />
      <FAQSection />

      {/* Weekly newsletter — lower-commitment alternative to the trial CTA.
          Anchor id="newsletter" is the scroll target for forwarded-email
          links (?subscribe=market_measured#newsletter). */}
      <section id="newsletter" className="bg-slate-50 py-16">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <MarketMeasuredSignup source="landing_below_faq" />
        </div>
      </section>

      <CTASection onGetStarted={handleGetStarted} />
      <Footer />

      {/* Login Modal */}
      {showLoginModal && (
        <LoginModal
          onClose={() => setShowLoginModal(false)}
          onSuccess={handleLoginSuccess}
          initialMode={isReturningVisitor ? 'login' : 'register'}
          selectedPlan={selectedPlan}
        />
      )}
    </div>
  );
}

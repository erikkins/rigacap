import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  TrendingUp, Zap, Shield, BarChart3, Bell, DollarSign,
  CheckCircle, ArrowRight, ChevronDown, ChevronUp, Star, Users, Target
} from 'lucide-react';
import { useAuth } from './contexts/AuthContext';
import LoginModal from './components/LoginModal';
import TrackRecordChart from './components/TrackRecordChart';

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
          Beat the Market with
          <span className="block bg-gradient-to-r from-yellow-200 via-yellow-300 to-orange-300 bg-clip-text text-transparent pb-2">
            AI-Powered Trading Signals
          </span>
        </h1>

        {/* Subheadline */}
        <p className="max-w-2xl mx-auto text-lg sm:text-xl text-blue-100 mb-4">
          Our Ensemble approach combines three proven factors — timing, momentum quality, and adaptive
          risk management — into one system that evolves through every market cycle.
        </p>
        <p className="text-sm text-blue-200/70 mb-8">~15 high-conviction signals per month — quality over quantity</p>

        {/* CTA Buttons */}
        <div className="flex flex-col sm:flex-row gap-4 justify-center items-center mb-12">
          <button
            onClick={onGetStarted}
            className="group flex items-center gap-2 px-8 py-4 bg-white text-indigo-600 font-semibold rounded-xl shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 transition-all"
          >
            Start Free Trial
            <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
          </button>
          <a
            href="/track-record"
            className="flex items-center gap-2 px-8 py-4 text-white/90 font-medium hover:text-white transition-colors"
          >
            View 5-Year Track Record
            <ArrowRight className="w-5 h-5" />
          </a>
          <a
            href="/market-regime"
            className="flex items-center gap-2 px-8 py-4 text-white/90 font-medium hover:text-white transition-colors"
          >
            Free Market Intelligence
            <ArrowRight className="w-5 h-5" />
          </a>
        </div>

        {/* Social proof */}
        <div className="flex flex-wrap justify-center items-center gap-8 text-sm text-blue-200">
          <div className="flex items-center gap-2">
            <Users className="w-5 h-5" />
            <span><strong className="text-white">2,500+</strong> Active Traders</span>
          </div>
          <div className="flex items-center gap-2">
            <Star className="w-5 h-5 text-yellow-300" />
            <span><strong className="text-white">15</strong> Years of Development</span>
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
          From signal to profit in 4 simple steps
        </p>
      </div>

      <div className="grid md:grid-cols-4 gap-8">
        {[
          { step: 1, title: 'Scan', desc: 'Our algorithms analyze 6,500+ stocks daily, ranking by momentum, quality, and market conditions' },
          { step: 2, title: 'Signal', desc: 'When criteria align, you get actionable alerts with entry, stop, and target levels' },
          { step: 3, title: 'Buy', desc: 'Execute through your broker with confidence — every signal includes entry, stop, and target levels' },
          { step: 4, title: 'Profit', desc: 'Trailing stops protect gains while letting winners run' },
        ].map(({ step, title, desc }) => (
          <div key={step} className="relative text-center">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-indigo-600 text-white text-2xl font-bold mb-4">
              {step}
            </div>
            {step < 4 && (
              <div className="hidden md:block absolute top-8 left-[60%] w-[80%] h-0.5 bg-indigo-200"></div>
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
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-8 text-center text-white">
        {[
          { value: '87.5%', label: 'Latest Year Return' },
          { value: '289%', label: '5-Year Return' },
          { value: '2.32', label: 'Sharpe Ratio' },
          { value: '80%', label: 'Win Rate' },
          { value: '-8.3%', label: 'Max Drawdown' },
        ].map(({ value, label }) => (
          <div key={label}>
            <div className="text-4xl lg:text-5xl font-bold mb-2">{value}</div>
            <div className="text-indigo-200">{label}</div>
          </div>
        ))}
      </div>
      <p className="text-indigo-200 text-sm mt-6 text-center max-w-2xl mx-auto">
        Walk-forward simulation results — year-by-year testing with no hindsight bias.
        Our Ensemble approach adapts through every market regime, from bull runs to bear markets.
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

const YearByYearSection = () => {
  const years = [
    { period: '2021-2022', returnPct: '+62.0%', sharpe: '1.21', maxDD: '-14.8%', color: 'text-emerald-600' },
    { period: '2022-2023', returnPct: '-13.2%', sharpe: '-1.38', maxDD: '-15.1%', color: 'text-red-600' },
    { period: '2023-2024', returnPct: '+22.2%', sharpe: '1.02', maxDD: '-13.6%', color: 'text-emerald-600' },
    { period: '2024-2025', returnPct: '+20.7%', sharpe: '0.89', maxDD: '-13.7%', color: 'text-emerald-600' },
    { period: '2025-2026', returnPct: '+87.5%', sharpe: '2.32', maxDD: '-8.3%', color: 'text-emerald-600' },
  ];

  return (
    <section className="py-20 bg-gradient-to-b from-white to-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-4">
            Consistent Performance, Year After Year
          </h2>
          <p className="text-lg text-gray-600 max-w-2xl mx-auto">
            Walk-forward simulation results with no hindsight bias. Each year tested independently.
          </p>
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 lg:gap-6">
          {years.map(({ period, returnPct, sharpe, maxDD, color }) => (
            <div key={period} className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100 text-center">
              <div className="text-sm font-medium text-gray-500 mb-3">{period}</div>
              <div className={`text-3xl font-bold mb-2 ${color}`}>{returnPct}</div>
              <div className="text-sm text-gray-500">
                <span className="block">Sharpe: {sharpe}</span>
                <span className="block">Max DD: {maxDD}</span>
              </div>
            </div>
          ))}
        </div>

        <p className="text-gray-400 text-xs mt-8 text-center max-w-2xl mx-auto">
          Walk-forward simulation results using the Ensemble strategy. Each 1-year period tested independently
          with biweekly rebalancing. Past performance does not guarantee future results.
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
    '6,500+ stocks scanned daily',
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

const TestimonialCard = ({ quote, author, role, avatar }) => (
  <div className="bg-white rounded-2xl p-8 shadow-lg border border-gray-100">
    <div className="flex gap-1 mb-4">
      {[1,2,3,4,5].map(i => (
        <Star key={i} className="w-5 h-5 text-yellow-400 fill-current" />
      ))}
    </div>
    <p className="text-gray-700 mb-6 leading-relaxed">"{quote}"</p>
    <div className="flex items-center gap-4">
      <div className="w-12 h-12 rounded-full bg-gradient-to-br from-indigo-400 to-purple-500 flex items-center justify-center text-white font-bold">
        {avatar}
      </div>
      <div>
        <div className="font-semibold text-gray-900">{author}</div>
        <div className="text-sm text-gray-500">{role}</div>
      </div>
    </div>
  </div>
);

const TestimonialsSection = () => (
  <section className="py-20 bg-gray-50">
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div className="text-center mb-16">
        <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-4">
          Loved by Traders Everywhere
        </h2>
        <p className="text-lg text-gray-600">
          See what our members are saying
        </p>
      </div>

      <div className="grid md:grid-cols-3 gap-8">
        <TestimonialCard
          quote="RigaCap's signals have completely changed how I trade. The ensemble approach is brilliant - I've made more in 3 months than the entire previous year."
          author="Michael R."
          role="Day Trader, Texas"
          avatar="MR"
        />
        <TestimonialCard
          quote="Finally, a trading tool that doesn't overwhelm me with complexity. Simple signals, clear targets. My portfolio is up 45% since I started."
          author="Sarah K."
          role="Part-time Investor, NYC"
          avatar="SK"
        />
        <TestimonialCard
          quote="The daily email digest is worth the subscription alone. I check it every evening and plan my next day's trades. Absolutely essential."
          author="James L."
          role="Swing Trader, Chicago"
          avatar="JL"
        />
      </div>
    </div>
  </section>
);

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
          answer="On average, we identify 3-8 quality signals per week from our universe of 6,500+ stocks. We prioritize quality over quantity - our focused approach targets only the best risk-adjusted opportunities."
        />
        <FAQItem
          question="What's your track record?"
          answer={<>Our Ensemble strategy has been validated through rigorous walk-forward simulations — year-by-year tests with no hindsight bias. We've navigated the 2021 bull run, 2022 bear market, 2023 recovery, and beyond — continuously adapting through each cycle. See our <a href="/track-record" className="text-indigo-400 hover:text-indigo-300 underline">full track record</a>.</>}
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
          <a href="/terms" className="hover:text-white transition-colors">Terms</a>
          <a href="/privacy" className="hover:text-white transition-colors">Privacy</a>
          <a href="/contact" className="hover:text-white transition-colors">Contact</a>
        </div>
        <div className="text-sm">
          &copy; {new Date().getFullYear()} RigaCap. All rights reserved.
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
  <svg width={size} height={size} viewBox="0 -128 1280 1280" className={className}>
    <g transform="matrix(5.266369152845155 0 0 5.266369152845155 639.7474324688749 511.4611892669334)">
      <g>
        <g transform="matrix(0.447842401165958 0 0 0.447842401165958 -22.37905439059665 -28.76675371508702)">
          <path fill="#67B3E9" d="M 215.4926147 348.1326294 C 215.4926147 341.4343262 220.5519104 335.9767151 227.0464782 335.2184448 L 241.64198299999998 278.3557434 C 238.3174896 275.98690799999997 236.13209529999997 272.1211853 236.13209529999997 267.7279358 C 236.13209529999997 260.5114746 241.98225399999998 254.66130070000003 249.19871519999998 254.66130070000003 C 255.88706969999998 254.66130070000003 261.3387146 259.70529180000005 262.1099243 266.18612670000005 L 309.18218989999997 278.15957640000005 C 311.5494384 274.8219604 315.4248962 272.62802120000003 319.82827749999996 272.62802120000003 C 323.99932849999993 272.62802120000003 327.67044059999995 274.6184387 330.06295769999997 277.6614685 L 391.39083859999994 258.8470459 C 391.8676757999999 252.0640717 397.4616393999999 246.6927338 404.36566159999995 246.6927338 C 405.08795159999994 246.6927338 405.78381349999995 246.79251100000002 406.47412109999993 246.9051972 L 420.4002074999999 223.132248 C 395.4410094999999 205.1961365 364.83840939999993 194.61979680000002 331.7564086999999 194.61979680000002 C 247.7547149999999 194.61979680000002 179.6581725999999 262.7163392 179.6581725999999 346.71804810000003 C 179.6581725999999 357.0606384 180.7147979999999 367.15197750000004 182.68611139999987 376.91201780000006 L 216.05313109999986 351.71652220000004 C 215.7245789 350.5704346 215.4926147 349.3842468 215.4926147 348.1326294 z"/>
        </g>
        <g transform="matrix(0.447842401165958 0 0 0.447842401165958 -11.05489640960161 -8.986830154000359)">
          <path fill="#3298E2" d="M 427.8859863 228.8635559 L 414.53790280000004 251.6500549 C 416.32159420000005 253.88394159999999 417.43228150000004 256.67834469999997 417.43228150000004 259.75936889999997 C 417.43228150000004 266.9758301 411.58212280000004 272.82598879999995 404.36566160000007 272.82598879999995 C 400.1946106000001 272.82598879999995 396.5232849000001 270.83538819999995 394.13079830000004 267.7923279 L 332.80288690000003 286.60696409999997 C 332.3262634 293.38973999999996 326.73229970000006 298.7614746 319.8282775 298.7614746 C 313.1401366 298.7614746 307.68869010000003 293.7178955 306.9169005 287.23745729999996 L 259.8444213 275.2633972 C 257.7556457 278.2080688 254.4786376 280.2024536 250.71150200000002 280.6423034 L 236.11599720000004 337.5046081 C 239.44068900000005 339.8734741 241.62588490000005 343.7393798 241.62588490000005 348.13262929999996 C 241.62588490000005 355.34927359999995 235.77590930000005 361.19924919999994 228.55924980000003 361.19924919999994 C 226.02284230000004 361.19924919999994 223.67565910000002 360.44515979999994 221.67153920000004 359.19454949999994 L 185.03727710000004 386.8588560999999 C 189.38798510000004 402.7608335999999 196.24627670000004 417.6278685999999 205.16970810000004 431.00256339999993 L 343.5092162 312.1214903999999 L 408.03659050000005 312.1214903999999 L 465.59317010000007 274.40634149999994 C 456.0913391 256.8570251 443.2310181 241.3963165 427.8859863 228.8635559 z"/>
        </g>
        <g transform="matrix(0.447842401165958 0 0 0.447842401165958 73.82936460708436 -37.11089695025285)">
          <polygon fill="#172554" points="-45.30519105000002,-14.32876589999998 45.30519104999996,-39.44079589999998 -12.74574285,39.44079590000001 -17.06205755000002,3.2839356000000066"/>
        </g>
        <g transform="matrix(0.447842401165958 0 0 0.447842401165958 -48.16632626991975 25.662112400608095)">
          <path fill="#172554" d="M 297.690155 513.3757935 C 291.8544922 512.1848145 286.1323242 510.6825867 280.5290222 508.9088135 L 280.5290222 405.3008118 L 233.16218569999998 446.0053406 L 233.16218569999998 485.1845703 C 189.93139649999998 454.3132019 161.66641239999998 403.77075190000005 161.66641239999998 346.71844480000004 C 161.66641239999998 321.47900390000007 167.2343445 297.52935790000004 177.14006049999998 275.9688110000001 L 153.41162119999998 275.9688110000001 C 144.68853769999998 297.8789672000001 139.83914199999998 321.7362060000001 139.83914199999998 346.71844480000004 C 139.83914199999998 452.54183960000006 225.93339549999996 538.6345215 331.7568056 538.6345215 C 336.23214740000003 538.6345215 340.6571657 538.4249878 345.0569765 538.1221314000001 L 345.0569765 349.8493347 L 297.69015520000005 390.5536499 L 297.69015520000005 513.3757935 z"/>
        </g>
        <g transform="matrix(0.447842401165958 0 0 0.447842401165958 41.62493388227972 31.445543033824293)">
          <path fill="#172554" d="M 523.1578979 333.3830872 L 501.27337639999996 333.3830872 C 501.617218 337.78863529999995 501.8457946 342.22619629999997 501.8457946 346.71844489999995 C 501.8457946 380.9995423 491.63201899999996 412.92395029999994 474.11251819999995 439.65051279999994 L 474.11251819999995 304.23995979999995 L 426.74587999999994 335.27807629999995 L 426.74587999999994 487.65298469999993 C 421.24215689999994 491.3716430999999 415.51919539999994 494.78399669999993 409.5847471999999 497.85028079999995 L 409.5847471999999 341.7442017 L 362.217926 341.7442017 L 362.217926 536.1913453 C 453.612976 521.5502931 523.6730957 442.17498789999996 523.6730957 346.7184449 C 523.6730957 342.2309875 523.4624023 337.7946167 523.1578979 333.3830872 z"/>
        </g>
        <g transform="matrix(0.447842401165958 0 0 0.447842401165958 -11.758155759779243 -60.819370702594256)">
          <path fill="#172554" d="M 331.7522278 169.315979 C 390.4548645 169.315979 442.57946780000003 197.9828644 474.8894653 242.0440826 L 483.06436149999996 239.7783813 C 449.4578552 192.3684234 394.1588134 161.3654937 331.75222769999993 161.3654937 C 258.06015009999993 161.3654937 194.28051749999995 204.5952758 164.42543019999994 267.0239257 L 173.28724659999995 267.0239257 C 202.5275574 209.120697 262.5750122 169.315979 331.7522278 169.315979 z"/>
        </g>
      </g>
    </g>
  </svg>
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
      console.log('LandingPage: User authenticated, navigating to /app');
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
    console.log('LandingPage: handleLoginSuccess called');
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
      <YearByYearSection />
      <PricingSection onGetStarted={handleGetStarted} />
      <TestimonialsSection />
      <FAQSection />
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

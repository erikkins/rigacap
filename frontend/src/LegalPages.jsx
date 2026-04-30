import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

const PageWrapper = ({ title, children }) => (
  <div className="min-h-screen bg-gray-950 text-gray-300">
    <nav className="bg-gray-900 border-b border-gray-800">
      <div className="max-w-4xl mx-auto px-4 py-4 flex items-center gap-4">
        <Link to="/" className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors">
          <ArrowLeft size={18} />
          <span className="text-sm">Back to RigaCap</span>
        </Link>
      </div>
    </nav>
    <div className="max-w-4xl mx-auto px-4 py-12">
      <h1 className="text-3xl font-bold text-white mb-8">{title}</h1>
      <div className="prose prose-invert prose-gray max-w-none space-y-6 text-gray-400 leading-relaxed">
        {children}
      </div>
      <div className="mt-16 pt-8 border-t border-gray-800 text-center text-sm text-gray-500">
        &copy; {new Date().getFullYear()} RigaCap, LLC. All rights reserved.
      </div>
    </div>
  </div>
);

const Section = ({ title, children }) => (
  <div>
    <h2 className="text-xl font-semibold text-white mt-8 mb-3">{title}</h2>
    {children}
  </div>
);

export function PrivacyPage() {
  return (
    <PageWrapper title="Privacy Policy">
      <p className="text-sm text-gray-500">Last updated: {new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}</p>

      <Section title="Overview">
        <p>RigaCap, LLC ("we", "us", "our") operates the rigacap.com website and related services. This policy describes how we collect, use, and protect your personal information.</p>
      </Section>

      <Section title="Information We Collect">
        <p><strong className="text-gray-200">Account Information:</strong> When you create an account, we collect your name, email address, and authentication credentials (via Google, Apple, or email sign-up).</p>
        <p><strong className="text-gray-200">Usage Data:</strong> We collect anonymized usage data including pages visited, features used, and interaction patterns to improve our service.</p>
        <p><strong className="text-gray-200">Payment Information:</strong> Payment processing is handled by Stripe. We do not store your credit card number or payment details on our servers. Stripe's privacy policy governs payment data handling.</p>
      </Section>

      <Section title="How We Use Your Information">
        <p>We use your information to:</p>
        <ul className="list-disc pl-6 space-y-1">
          <li>Provide and maintain our trading signal service</li>
          <li>Send you trading alerts, daily summaries, and breakout notifications you've opted into</li>
          <li>Process your subscription and manage your account</li>
          <li>Improve our algorithms and user experience</li>
          <li>Respond to support requests</li>
        </ul>
      </Section>

      <Section title="Email Communications">
        <p>Subscribers receive trading signal emails including daily summaries and breakout alerts. You can unsubscribe from non-essential emails at any time via the unsubscribe link in each email or by contacting us directly.</p>
      </Section>

      <Section title="Data Sharing">
        <p>We do not sell, rent, or trade your personal information. We share data only with:</p>
        <ul className="list-disc pl-6 space-y-1">
          <li><strong className="text-gray-200">Stripe</strong> — for payment processing</li>
          <li><strong className="text-gray-200">AWS</strong> — for hosting and infrastructure</li>
          <li><strong className="text-gray-200">Google/Apple</strong> — for authentication (only the data needed to verify your identity)</li>
        </ul>
      </Section>

      <Section title="Data Security">
        <p>We use industry-standard security measures including encrypted connections (TLS/SSL), secure cloud infrastructure (AWS), and access controls to protect your data. No system is 100% secure, but we take reasonable precautions to safeguard your information.</p>
      </Section>

      <Section title="Data Retention">
        <p>We retain your account data for as long as your account is active. If you delete your account, we remove your personal information within 30 days, except where retention is required by law.</p>
      </Section>

      <Section title="Your Rights">
        <p>You may request to access, update, or delete your personal data at any time by contacting us at the email below. California residents have additional rights under the CCPA, including the right to know what data we collect and the right to opt out of data sales (we do not sell data).</p>
      </Section>

      <Section title="Cookies">
        <p>We use essential cookies for authentication and session management. With your consent, we also use Google Analytics (GA4) to understand how visitors use our site. You can change your cookie preferences at any time using the cookie banner.</p>
      </Section>

      <Section title="Changes to This Policy">
        <p>We may update this policy from time to time. Material changes will be communicated via email or a notice on our website.</p>
      </Section>

      <Section title="Contact">
        <p>For privacy-related questions or requests, contact us at <a href="mailto:info@rigacap.com" className="text-amber-400 hover:text-amber-300">info@rigacap.com</a>.</p>
      </Section>
    </PageWrapper>
  );
}

export function TermsPage() {
  return (
    <PageWrapper title="Terms of Service">
      <p className="text-sm text-gray-500">Last updated: {new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}</p>

      <Section title="Agreement">
        <p>By accessing or using RigaCap ("the Service"), you agree to be bound by these Terms of Service. If you do not agree, do not use the Service.</p>
      </Section>

      <Section title="Description of Service">
        <p>RigaCap provides algorithmic trading signals generated by quantitative models using walk-forward testing methodology. The Service includes a web dashboard, email alerts, and related tools for viewing and acting on trading signals.</p>
      </Section>

      <Section title="Not Investment Advice">
        <p className="text-amber-400/80 font-medium">RigaCap, LLC is not a registered investment advisor, broker-dealer, or financial planner. The signals, data, content, and methodology provided through the Service are for information purposes only and are not a solicitation to invest, purchase, or sell securities in which RigaCap has an interest. They do not constitute investment advice, financial advice, trading advice, or any other kind of advice.</p>
        <p>You are solely responsible for your own investment decisions. Trading stocks involves substantial risk of loss and is not suitable for every investor. Past performance of our algorithms does not guarantee future results.</p>
      </Section>

      <Section title="Accounts">
        <p>You must provide accurate information when creating an account. You are responsible for maintaining the security of your account credentials. You must be at least 18 years old to use the Service.</p>
      </Section>

      <Section title="Subscriptions and Billing">
        <p>Paid features require a subscription. Subscriptions renew automatically unless canceled before the renewal date. Refunds are handled on a case-by-case basis — contact us if you're unsatisfied and we'll work something out.</p>
        <p>We reserve the right to change pricing with 30 days' notice to existing subscribers.</p>
      </Section>

      <Section title="Acceptable Use">
        <p>You agree not to:</p>
        <ul className="list-disc pl-6 space-y-1">
          <li>Redistribute, resell, or publicly share trading signals from the Service</li>
          <li>Use automated tools to scrape or extract data from the Service</li>
          <li>Attempt to reverse-engineer our algorithms or proprietary methods</li>
          <li>Use the Service for any unlawful purpose</li>
          <li>Interfere with the operation of the Service</li>
        </ul>
      </Section>

      <Section title="Intellectual Property">
        <p>All content, algorithms, software, and branding associated with RigaCap are our intellectual property. Your subscription grants you a personal, non-transferable license to use the Service. It does not grant ownership of any content or technology.</p>
      </Section>

      <Section title="Limitation of Liability">
        <p>To the maximum extent permitted by law, RigaCap, LLC shall not be liable for any indirect, incidental, special, consequential, or punitive damages, including but not limited to loss of profits, trading losses, or data loss, arising from your use of the Service.</p>
        <p>Our total liability for any claim related to the Service is limited to the amount you paid us in the 12 months preceding the claim.</p>
      </Section>

      <Section title="Disclaimer of Warranties">
        <p>The Service is provided "as is" and "as available" without warranties of any kind, either express or implied. We do not warrant that signals will be accurate, profitable, or uninterrupted.</p>
      </Section>

      <Section title="Termination">
        <p>We may suspend or terminate your account if you violate these Terms. You may cancel your account at any time. Upon termination, your right to use the Service ceases immediately.</p>
      </Section>

      <Section title="Governing Law">
        <p>These Terms are governed by the laws of the State of Delaware, without regard to conflict of law principles.</p>
      </Section>

      <Section title="Changes to Terms">
        <p>We may update these Terms from time to time. Continued use of the Service after changes constitutes acceptance of the updated Terms.</p>
      </Section>

      <Section title="Contact">
        <p>Questions about these Terms? Contact us at <a href="mailto:info@rigacap.com" className="text-amber-400 hover:text-amber-300">info@rigacap.com</a>.</p>
      </Section>
    </PageWrapper>
  );
}

export function ContactPage() {
  return (
    <PageWrapper title="Contact Us">
      <p>We'd love to hear from you. Whether you have a question about signals, your subscription, or just want to say hi — here's how to reach us.</p>

      <Section title="Email">
        <p>For all inquiries — general questions, support, privacy requests, or feedback:</p>
        <p><a href="mailto:info@rigacap.com" className="text-amber-400 hover:text-amber-300">info@rigacap.com</a></p>
      </Section>

      <Section title="Social Media">
        <div className="space-y-2">
          <p><a href="https://twitter.com/rigacap" target="_blank" rel="noopener noreferrer" className="text-amber-400 hover:text-amber-300">Twitter / X — @rigacap</a></p>
          <p><a href="https://instagram.com/rigacapital" target="_blank" rel="noopener noreferrer" className="text-amber-400 hover:text-amber-300">Instagram — @rigacapital</a></p>
        </div>
      </Section>

      <Section title="Mailing Address">
        <p className="text-gray-500">RigaCap, LLC<br/>United States</p>
      </Section>

      <p className="text-sm text-gray-500 mt-8">We typically respond within 1 business day.</p>
    </PageWrapper>
  );
}

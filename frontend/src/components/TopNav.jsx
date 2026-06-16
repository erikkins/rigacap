import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Menu, X } from 'lucide-react';

// Shared site nav. Editorial-publication convention: logo top-left serves as
// the home link; nav items are content destinations only. Layout stays
// fixed-width across pages — current page is rendered as an active span,
// not removed, so the link slots don't reflow.
//
// Pages with login-modal CTA pass `onGetStarted`; pages without it (blog,
// about, etc.) get the default Start Trial → /  navigation.

const NAV_ITEMS = [
  { label: 'Methodology', to: '/methodology' },
  { label: 'Track Record', to: '/track-record' },
  { label: 'Newsletter', to: '/newsletter' },
  { label: 'Blog', to: '/blog' },
  { label: 'Pricing', href: '/#pricing' },
];

const LogoMark = () => (
  <svg className="w-7 h-7 shrink-0 relative top-[2px]" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 1024">
    <g transform="matrix(5.27 0 0 5.27 640 511)"><g>
      <g transform="matrix(0.448 0 0 0.448 -22.4 -28.8)"><path fill="#7A2430" transform="translate(-300,-286)" d="M215.49 348.13C215.49 341.43 220.55 335.98 227.05 335.22L241.64 278.36C238.32 275.99 236.13 272.12 236.13 267.73C236.13 260.51 241.98 254.66 249.2 254.66C255.89 254.66 261.34 259.71 262.11 266.19L309.18 278.16C311.55 274.82 315.42 272.63 319.83 272.63C324 272.63 327.67 274.62 330.06 277.66L391.39 258.85C391.87 252.06 397.46 246.69 404.37 246.69C405.09 246.69 405.78 246.79 406.47 246.91L420.4 223.13C395.44 205.2 364.84 194.62 331.76 194.62C247.75 194.62 179.66 262.72 179.66 346.72C179.66 357.06 180.71 367.15 182.69 376.91L216.05 351.72C215.72 350.57 215.49 349.38 215.49 348.13z"/></g>
      <g transform="matrix(0.448 0 0 0.448 -11.1 -9)"><path fill="#7A2430" transform="translate(-325,-330)" d="M427.89 228.86L414.54 251.65C416.32 253.88 417.43 256.68 417.43 259.76C417.43 266.98 411.58 272.83 404.37 272.83C400.19 272.83 396.52 270.84 394.13 267.79L332.8 286.61C332.33 293.39 326.73 298.76 319.83 298.76C313.14 298.76 307.69 293.72 306.92 287.24L259.84 275.26C257.76 278.21 254.48 280.2 250.71 280.64L236.12 337.5C239.44 339.87 241.63 343.74 241.63 348.13C241.63 355.35 235.78 361.2 228.56 361.2C226.02 361.2 223.68 360.45 221.67 359.19L185.04 386.86C189.39 402.76 196.25 417.63 205.17 431L343.51 312.12L408.04 312.12L465.59 274.41C456.09 256.86 443.23 241.4 427.89 228.86z"/></g>
      <g transform="matrix(0.448 0 0 0.448 73.8 -37.1)"><polygon fill="#7A2430" points="-45.31,-14.33 45.31,-39.44 -12.75,39.44 -17.06,3.28"/></g>
      <g transform="matrix(0.448 0 0 0.448 -48.2 25.7)"><path fill="#141210" transform="translate(-242,-407)" d="M297.69 513.38C291.85 512.18 286.13 510.68 280.53 508.91L280.53 405.3L233.16 446.01L233.16 485.18C189.93 454.31 161.67 403.77 161.67 346.72C161.67 321.48 167.23 297.53 177.14 275.97L153.41 275.97C144.69 297.88 139.84 321.74 139.84 346.72C139.84 452.54 225.93 538.63 331.76 538.63C336.23 538.63 340.66 538.42 345.06 538.12L345.06 349.85L297.69 390.55L297.69 513.38z"/></g>
      <g transform="matrix(0.448 0 0 0.448 41.6 31.4)"><path fill="#141210" transform="translate(-443,-420)" d="M523.16 333.38L501.27 333.38C501.62 337.79 501.85 342.23 501.85 346.72C501.85 381 491.63 412.92 474.11 439.65L474.11 304.24L426.75 335.28L426.75 487.65C421.24 491.37 415.52 494.78 409.58 497.85L409.58 341.74L362.22 341.74L362.22 536.19C453.61 521.55 523.67 442.17 523.67 346.72C523.67 342.23 523.46 337.79 523.16 333.38z"/></g>
      <g transform="matrix(0.448 0 0 0.448 -11.8 -60.8)"><path fill="#141210" transform="translate(-324,-214)" d="M331.75 169.32C390.45 169.32 442.58 197.98 474.89 242.04L483.06 239.78C449.46 192.37 394.16 161.37 331.75 161.37C258.06 161.37 194.28 204.6 164.43 267.02L173.29 267.02C202.53 209.12 262.58 169.32 331.75 169.32z"/></g>
    </g></g>
  </svg>
);

export default function TopNav({ onGetStarted }) {
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);

  return (
    <nav className="sticky top-0 z-50 bg-paper/95 backdrop-blur-sm border-b border-rule">
      <div className="max-w-[1120px] mx-auto px-4 sm:px-8 py-5 flex items-center justify-between">
        <Link to="/" className="flex items-baseline gap-2.5 no-underline">
          <LogoMark />
          <span className="font-display text-2xl font-semibold text-ink tracking-tight" style={{ fontVariationSettings: '"opsz" 144' }}>
            RigaCap<span className="text-claret">.</span>
          </span>
        </Link>
        <div className="flex items-center gap-4 sm:gap-7">
          {NAV_ITEMS.map((item) => {
            // Active matching: anchor links (e.g. /#pricing) compare on
            // pathname only — so /#pricing is active when on /, not on
            // /track-record. Standard route links match exact pathname.
            const isActive = item.to ? pathname === item.to : false;
            const baseCls = 'hidden sm:inline text-[0.9rem] no-underline transition-colors';
            if (isActive) {
              // Non-clickable active state — preserves layout spacing while
              // signalling current page. Cursor:default avoids hover pointer.
              return (
                <span
                  key={item.label}
                  className={`${baseCls} text-ink font-medium`}
                  style={{ cursor: 'default' }}
                  aria-current="page"
                >
                  {item.label}
                </span>
              );
            }
            if (item.href) {
              // Anchor links use raw <a> for hash navigation
              return (
                <a key={item.label} href={item.href} className={`${baseCls} text-ink-mute hover:text-ink`}>
                  {item.label}
                </a>
              );
            }
            return (
              <Link key={item.label} to={item.to} className={`${baseCls} text-ink-mute hover:text-ink`}>
                {item.label}
              </Link>
            );
          })}
          {onGetStarted ? (
            <button
              onClick={() => onGetStarted('founding')}
              className="bg-ink text-paper px-4 py-2.5 text-[0.9rem] font-medium rounded-[2px] hover:bg-claret transition-colors"
            >
              Start Trial
            </button>
          ) : (
            <Link
              to="/"
              className="bg-ink text-paper px-4 py-2.5 text-[0.9rem] font-medium rounded-[2px] hover:bg-claret transition-colors no-underline"
            >
              Start Trial
            </Link>
          )}
          {/* Mobile hamburger — reveals NAV_ITEMS, which are `hidden sm:inline`.
              Without this the nav links vanished entirely on phones (the header
              kept only the logo + Start Trial). Added Jun 16 2026. */}
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            className="sm:hidden -mr-1 p-1 text-ink"
            aria-label={open ? 'Close menu' : 'Open menu'}
            aria-expanded={open}
          >
            {open ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </div>
      </div>
      {/* Mobile menu panel */}
      {open && (
        <div className="sm:hidden border-t border-rule bg-paper px-4 pb-3 pt-1">
          {NAV_ITEMS.map((item) => {
            const isActive = item.to ? pathname === item.to : false;
            const cls = `block py-2.5 text-[1rem] no-underline ${isActive ? 'text-ink font-medium' : 'text-ink-mute'}`;
            if (item.href) {
              return (
                <a key={item.label} href={item.href} className={cls} onClick={() => setOpen(false)}>
                  {item.label}
                </a>
              );
            }
            return (
              <Link key={item.label} to={item.to} className={cls} onClick={() => setOpen(false)}>
                {item.label}
              </Link>
            );
          })}
        </div>
      )}
    </nav>
  );
}

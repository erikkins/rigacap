#!/usr/bin/env node
/**
 * Build-time prerender for SEO. Generates a dist/<route>/index.html for every
 * known marketing route, with route-specific <title>, <meta description>,
 * <link canonical>, and OpenGraph tags injected into the head.
 *
 * Run after `vite build` (already wired into npm run build).
 *
 * Why: rigacap.com is a React SPA. Vite emits a single dist/index.html with
 * a hardcoded title and a canonical pointing at the apex. Crawlers (Google,
 * Bing) hit /blog/2022-story, get the homepage HTML, and conclude every
 * subroute is a duplicate of /. They mark them "Discovered — currently not
 * indexed" and never index them.
 *
 * Pairs with a CloudFront function that rewrites extensionless URIs
 * (/blog/2022-story → /blog/2022-story/index.html) so S3 actually serves
 * the prerendered file. Without that function, the file is invisible.
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DIST = path.resolve(__dirname, '../dist');
const ORIGIN = 'https://rigacap.com';
const DEFAULT_OG_IMAGE = 'https://rigacap.com/og-card.png';

// Each route gets its own static HTML with the correct meta. Add new
// marketing routes here; subroutes that aren't listed continue to receive
// the generic dist/index.html (which is fine — JS hydrates the right UI;
// SEO is just less specific until the route is added below).
const ROUTES = [
  {
    path: '/track-record',
    title: 'Track Record — RigaCap',
    description: 'Walk-forward verified results across multiple market regimes. See every signal, every exit, in plain English.',
  },
  {
    path: '/track-record-v1',
    title: 'Track Record (v1) — RigaCap',
    description: 'Earlier track-record format. Walk-forward results, 2021–2026.',
  },
  {
    path: '/track-record-10y',
    title: '10-Year Track Record — RigaCap',
    description: 'Full ten-year walk-forward backtest. Performance, drawdowns, and what worked through every regime.',
  },
  {
    path: '/methodology',
    title: 'Methodology — RigaCap',
    description: 'How the system finds setups, sizes positions, and exits. Quantitative discipline, no discretionary overrides.',
  },
  {
    path: '/methodology-v1',
    title: 'Methodology (v1) — RigaCap',
    description: 'Earlier methodology page. The signal-generation framework explained.',
  },
  {
    path: '/about',
    title: 'About — RigaCap',
    description: 'A signal service for retail investors who want quantitative discipline without quitting their day job.',
  },
  {
    path: '/blog',
    title: 'Blog — RigaCap',
    description: 'Notes on market regimes, walk-forward research, and trading discipline. Written for the investor who reads.',
  },
  {
    path: '/blog/2022-story',
    title: 'How the System Saw 2022 Coming — RigaCap',
    description: 'The bear market that wiped out passive investors. How a regime-aware momentum system stayed in cash through the worst of it.',
  },
  {
    path: '/blog/backtests',
    title: 'Reading a Backtest Honestly — RigaCap',
    description: 'Why most backtests lie, and what a walk-forward result actually proves. The questions to ask before you trust a number.',
  },
  {
    path: '/blog/market-crash',
    title: 'When the Market Crashes, What Should You Do? — RigaCap',
    description: 'The panic regime, the trailing stop, and why exits matter more than entries during a crash.',
  },
  {
    path: '/blog/market-regimes',
    title: 'Seven Market Regimes — RigaCap',
    description: 'Strong Bull, Weak Bull, Rotating Bull, Range-Bound, Weak Bear, Panic Crash, Recovery. Why they matter and how the system reads them.',
  },
  {
    path: '/blog/market-regime-guide',
    title: 'A Practical Guide to Market Regimes — RigaCap',
    description: 'Reading the tape with quantitative tools. SPY vs MA200, breadth, VIX — what each signal actually means.',
  },
  {
    path: '/blog/trailing-stops',
    title: 'The Case for the Trailing Stop — RigaCap',
    description: 'Why a 12% trailing stop beats a fixed stop-loss. How letting winners run quietly compounds your returns.',
  },
  {
    path: '/blog/momentum-trading',
    title: 'Why Momentum Works — RigaCap',
    description: 'The behavioral and structural reasons momentum has persisted as a factor across decades.',
  },
  {
    path: '/blog/walk-forward-results',
    title: 'Walk-Forward Results — RigaCap',
    description: 'No hindsight, no curve fitting. How the system performed in out-of-sample windows across multiple regimes.',
  },
  {
    path: '/blog/we-called-it-mrna',
    title: 'We Called It: MRNA — RigaCap',
    description: 'The setup, the entry, the exit. A walk-through of an MRNA signal from regime read to trailing-stop close.',
  },
  {
    path: '/blog/we-called-it-tgtx',
    title: 'We Called It: TGTX — RigaCap',
    description: 'A TGTX signal from start to finish. Why the system picked it up and what it took to hold through the noise.',
  },
  {
    path: '/market-regime',
    title: 'Live Market Regime — RigaCap',
    description: 'Where the market is right now, how the system is reading it, and what that means for new positions.',
  },
  {
    path: '/privacy',
    title: 'Privacy Policy — RigaCap',
    description: 'How RigaCap handles your data. GDPR and CCPA compliant. Plain-English summary above the legal language.',
  },
  {
    path: '/terms',
    title: 'Terms of Service — RigaCap',
    description: 'Subscription terms, financial disclaimer, and use restrictions. Signals only — not financial advice.',
  },
  {
    path: '/contact',
    title: 'Contact — RigaCap',
    description: 'Questions, feedback, or press? Reach out.',
  },
  {
    path: '/newsletter',
    title: 'The Market, Measured — RigaCap',
    description: 'Weekly system commentary. What the system saw, what it did, and what it is watching. Plain English.',
  },
];

/**
 * Replace a single tag's attribute value in the HTML head, by selector
 * pattern. Lightweight regex-based — matches the patterns Vite emits in
 * index.html. If the tag doesn't exist, it is appended just before </head>.
 */
function setMetaInHtml(html, opts) {
  const { title, description, canonical, ogTitle, ogDescription, ogUrl, ogImage } = opts;

  let out = html;

  if (title) {
    out = out.replace(/<title>[^<]*<\/title>/i, `<title>${escapeHtml(title)}</title>`);
  }
  if (canonical) {
    out = out.replace(
      /<link\s+rel="canonical"\s+href="[^"]*"\s*\/>/i,
      `<link rel="canonical" href="${escapeAttr(canonical)}" />`
    );
  }
  if (description) {
    out = replaceOrInsertMeta(out, 'name="description"', description);
  }
  if (ogTitle) {
    out = replaceOrInsertMeta(out, 'property="og:title"', ogTitle);
  }
  if (ogDescription) {
    out = replaceOrInsertMeta(out, 'property="og:description"', ogDescription);
  }
  if (ogUrl) {
    out = replaceOrInsertMeta(out, 'property="og:url"', ogUrl);
  }
  if (ogImage) {
    out = replaceOrInsertMeta(out, 'property="og:image"', ogImage);
  }

  return out;
}

function replaceOrInsertMeta(html, attrPattern, content) {
  const escaped = attrPattern.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const re = new RegExp(`<meta\\s+${escaped}\\s+content="[^"]*"\\s*\\/?>`, 'i');
  if (re.test(html)) {
    return html.replace(re, `<meta ${attrPattern} content="${escapeAttr(content)}" />`);
  }
  // Insert before </head> if not present
  return html.replace(
    /<\/head>/i,
    `  <meta ${attrPattern} content="${escapeAttr(content)}" />\n</head>`
  );
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function escapeAttr(s) {
  return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;');
}

// ──────────────────────────────────────────────────────────────────

const indexHtmlPath = path.join(DIST, 'index.html');
if (!fs.existsSync(indexHtmlPath)) {
  console.error(`prerender: ${indexHtmlPath} not found — run vite build first`);
  process.exit(1);
}
const indexHtml = fs.readFileSync(indexHtmlPath, 'utf-8');

let written = 0;
for (const route of ROUTES) {
  const canonical = ORIGIN + route.path;
  const html = setMetaInHtml(indexHtml, {
    title: route.title,
    description: route.description,
    canonical,
    ogTitle: route.title,
    ogDescription: route.description,
    ogUrl: canonical,
    ogImage: DEFAULT_OG_IMAGE,
  });

  const targetDir = path.join(DIST, route.path.replace(/^\//, ''));
  fs.mkdirSync(targetDir, { recursive: true });
  fs.writeFileSync(path.join(targetDir, 'index.html'), html);
  written += 1;
}

console.log(`prerender: wrote ${written} static route files under dist/`);

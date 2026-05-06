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
import { execSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DIST = path.resolve(__dirname, '../dist');
const FRONTEND_ROOT = path.resolve(__dirname, '..');
const ORIGIN = 'https://rigacap.com';
const DEFAULT_OG_IMAGE = 'https://rigacap.com/og-card.png';
const TODAY = new Date().toISOString().slice(0, 10);

// Each route gets its own static HTML with the correct meta. Add new
// marketing routes here; subroutes that aren't listed continue to receive
// the generic dist/index.html (which is fine — JS hydrates the right UI;
// SEO is just less specific until the route is added below).
const ROUTES = [
  {
    path: '/track-record',
    title: 'Track Record — RigaCap',
    description: 'Walk-forward verified results across multiple market regimes. See every signal, every exit, in plain English.',
    source: 'src/TrackRecordPageV2.jsx',
    priority: 0.9, changefreq: 'weekly',
  },
  {
    path: '/track-record-v1',
    title: 'Track Record (v1) — RigaCap',
    description: 'Earlier track-record format. Walk-forward results, 2021–2026.',
    source: 'src/TrackRecordPage.jsx',
    priority: 0.5, changefreq: 'monthly',
  },
  {
    path: '/track-record-10y',
    title: '10-Year Track Record — RigaCap',
    description: 'Full ten-year walk-forward backtest. Performance, drawdowns, and what worked through every regime.',
    source: 'src/TrackRecord10YPage.jsx',
    priority: 0.8, changefreq: 'weekly',
  },
  {
    path: '/methodology',
    title: 'Methodology — RigaCap',
    description: 'How the system finds setups, sizes positions, and exits. Quantitative discipline, no discretionary overrides.',
    source: 'src/MethodologyPageV2.jsx',
    priority: 0.9, changefreq: 'weekly',
  },
  {
    path: '/methodology-v1',
    title: 'Methodology (v1) — RigaCap',
    description: 'Earlier methodology page. The signal-generation framework explained.',
    source: 'src/MethodologyPage.jsx',
    priority: 0.5, changefreq: 'monthly',
  },
  {
    path: '/about',
    title: 'About — RigaCap',
    description: 'A signal service for retail investors who want quantitative discipline without quitting their day job.',
    source: 'src/AboutPage.jsx',
    priority: 0.7, changefreq: 'monthly',
  },
  {
    path: '/blog',
    title: 'Blog — RigaCap',
    description: 'Notes on market regimes, walk-forward research, and trading discipline. Written for the investor who reads.',
    source: 'src/BlogIndexPage.jsx',
    priority: 0.9, changefreq: 'weekly',
  },
  {
    path: '/blog/2022-story',
    title: 'How the System Saw 2022 Coming — RigaCap',
    description: 'The bear market that wiped out passive investors. How a regime-aware momentum system stayed in cash through the worst of it.',
    source: 'src/Blog2022StoryPage.jsx',
    priority: 0.8, changefreq: 'monthly',
  },
  {
    path: '/blog/backtests',
    title: 'Reading a Backtest Honestly — RigaCap',
    description: 'Why most backtests lie, and what a walk-forward result actually proves. The questions to ask before you trust a number.',
    source: 'src/BlogBacktestsPage.jsx',
    priority: 0.8, changefreq: 'monthly',
  },
  {
    path: '/blog/market-crash',
    title: 'When the Market Crashes, What Should You Do? — RigaCap',
    description: 'The panic regime, the trailing stop, and why exits matter more than entries during a crash.',
    source: 'src/BlogMarketCrashPage.jsx',
    priority: 0.8, changefreq: 'monthly',
  },
  {
    path: '/blog/market-regimes',
    title: 'Seven Market Regimes — RigaCap',
    description: 'Strong Bull, Weak Bull, Rotating Bull, Range-Bound, Weak Bear, Panic Crash, Recovery. Why they matter and how the system reads them.',
    source: 'src/BlogMarketRegimesPage.jsx',
    priority: 0.8, changefreq: 'monthly',
  },
  {
    path: '/blog/market-regime-guide',
    title: 'A Practical Guide to Market Regimes — RigaCap',
    description: 'Reading the tape with quantitative tools. SPY vs MA200, breadth, VIX — what each signal actually means.',
    source: 'src/BlogMarketRegimeGuidePage.jsx',
    priority: 0.8, changefreq: 'monthly',
  },
  {
    path: '/blog/trailing-stops',
    title: 'The Case for the Trailing Stop — RigaCap',
    description: 'Why a 12% trailing stop beats a fixed stop-loss. How letting winners run quietly compounds your returns.',
    source: 'src/BlogTrailingStopsPage.jsx',
    priority: 0.8, changefreq: 'monthly',
  },
  {
    path: '/blog/momentum-trading',
    title: 'Why Momentum Works — RigaCap',
    description: 'The behavioral and structural reasons momentum has persisted as a factor across decades.',
    source: 'src/BlogMomentumTradingPage.jsx',
    priority: 0.8, changefreq: 'monthly',
  },
  {
    path: '/blog/walk-forward-results',
    title: 'Walk-Forward Results — RigaCap',
    description: 'No hindsight, no curve fitting. How the system performed in out-of-sample windows across multiple regimes.',
    source: 'src/BlogWalkForwardResultsPage.jsx',
    priority: 0.9, changefreq: 'monthly',
  },
  {
    path: '/blog/we-called-it-mrna',
    title: 'We Called It: MRNA — RigaCap',
    description: 'The setup, the entry, the exit. A walk-through of an MRNA signal from regime read to trailing-stop close.',
    source: 'src/BlogWeCalledItMRNAPage.jsx',
    priority: 0.8, changefreq: 'monthly',
  },
  {
    path: '/blog/we-called-it-tgtx',
    title: 'We Called It: TGTX — RigaCap',
    description: 'A TGTX signal from start to finish. Why the system picked it up and what it took to hold through the noise.',
    source: 'src/BlogWeCalledItTGTXPage.jsx',
    priority: 0.8, changefreq: 'monthly',
  },
  {
    path: '/market-regime',
    title: 'Live Market Regime — RigaCap',
    description: 'Where the market is right now, how the system is reading it, and what that means for new positions.',
    source: 'src/MarketRegimePage.jsx',
    priority: 0.8, changefreq: 'daily',
  },
  {
    path: '/privacy',
    title: 'Privacy Policy — RigaCap',
    description: 'How RigaCap handles your data. GDPR and CCPA compliant. Plain-English summary above the legal language.',
    source: 'src/PrivacyPage.jsx',
    priority: 0.4, changefreq: 'monthly',
  },
  {
    path: '/terms',
    title: 'Terms of Service — RigaCap',
    description: 'Subscription terms, financial disclaimer, and use restrictions. Signals only — not financial advice.',
    source: 'src/TermsPage.jsx',
    priority: 0.4, changefreq: 'monthly',
  },
  {
    path: '/contact',
    title: 'Contact — RigaCap',
    description: 'Questions, feedback, or press? Reach out.',
    source: 'src/ContactPage.jsx',
    priority: 0.5, changefreq: 'monthly',
  },
  {
    path: '/newsletter',
    title: 'The Market, Measured — RigaCap',
    description: 'Weekly system commentary. What the system saw, what it did, and what it is watching. Plain English.',
    source: 'src/NewsletterPage.jsx',
    priority: 0.9, changefreq: 'weekly',
  },
];

// Homepage isn't in ROUTES (since dist/index.html is already correct from
// Vite), but it does belong in the sitemap.
const HOMEPAGE_SITEMAP_ENTRY = {
  path: '/',
  source: 'index.html',
  priority: 1.0,
  changefreq: 'daily',
};

/**
 * Last commit date for a source file, ISO-8601 (YYYY-MM-DD).
 * Falls back to today's date if git isn't available or the file is new.
 */
function gitLastModified(relPath) {
  try {
    const out = execSync(
      `git log -1 --format=%cs -- "${relPath}"`,
      { cwd: FRONTEND_ROOT, encoding: 'utf-8', stdio: ['ignore', 'pipe', 'ignore'] }
    ).trim();
    if (out) return out;
  } catch (_e) {
    // git missing or file untracked
  }
  return TODAY;
}

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

// ──────────────────────────────────────────────────────────────────
// sitemap.xml — generated each build with per-page git lastmod dates
// so Google sees real freshness signals. Replaces the hand-edited
// frontend/public/sitemap.xml that had everything stuck on 2026-04-18.
// ──────────────────────────────────────────────────────────────────

const sitemapEntries = [HOMEPAGE_SITEMAP_ENTRY, ...ROUTES].map((r) => ({
  loc: ORIGIN + r.path,
  lastmod: gitLastModified(r.source),
  changefreq: r.changefreq,
  priority: r.priority,
}));

const sitemap = [
  '<?xml version="1.0" encoding="UTF-8"?>',
  '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
  ...sitemapEntries.map((e) => [
    '  <url>',
    `    <loc>${e.loc}</loc>`,
    `    <lastmod>${e.lastmod}</lastmod>`,
    `    <changefreq>${e.changefreq}</changefreq>`,
    `    <priority>${e.priority.toFixed(1)}</priority>`,
    '  </url>',
  ].join('\n')),
  '</urlset>',
  '',
].join('\n');

fs.writeFileSync(path.join(DIST, 'sitemap.xml'), sitemap);
console.log(`prerender: wrote sitemap.xml with ${sitemapEntries.length} URLs (lastmod from git per-file)`);

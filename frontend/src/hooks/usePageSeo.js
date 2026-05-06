/**
 * Per-route SEO hook for the React SPA.
 *
 * Runs AFTER the build-time prerender (frontend/scripts/prerender-routes.mjs)
 * as a safety net:
 *   - For routes in the prerender list: the static HTML already carries the
 *     correct meta tags, this hook is a no-op practically (Google reads the
 *     static HTML on the first crawl).
 *   - For routes NOT in the prerender list: this hook updates document.title
 *     and the canonical/description/OG meta tags client-side. Google's
 *     second-pass renderer (which runs JS) picks up the corrected meta.
 *   - On SPA navigation between routes: each page component calls this hook
 *     with its own meta, so the document head updates as the user navigates.
 *
 * No new dependencies — pure DOM manipulation.
 */

import { useEffect } from 'react';

const ORIGIN = 'https://rigacap.com';

function setMetaContent(selector, attrName, attrValue, content) {
  let el = document.head.querySelector(selector);
  if (!el) {
    el = document.createElement('meta');
    el.setAttribute(attrName, attrValue);
    document.head.appendChild(el);
  }
  el.setAttribute('content', content);
}

function setLinkHref(rel, href) {
  let el = document.head.querySelector(`link[rel="${rel}"]`);
  if (!el) {
    el = document.createElement('link');
    el.setAttribute('rel', rel);
    document.head.appendChild(el);
  }
  el.setAttribute('href', href);
}

/**
 * Update document head meta tags for the current route.
 *
 * @param {Object} opts
 * @param {string} opts.title - <title> text
 * @param {string} opts.description - meta description
 * @param {string} [opts.path] - URL path; canonical + og:url derive from this. Defaults to current pathname.
 * @param {string} [opts.image] - OG image URL. Defaults to /og-card.png.
 */
export function usePageSeo({ title, description, path, image }) {
  useEffect(() => {
    const pathname = path || (typeof window !== 'undefined' ? window.location.pathname : '/');
    const canonical = ORIGIN + pathname;
    const ogImage = image || `${ORIGIN}/og-card.png`;

    if (title) document.title = title;
    if (description) {
      setMetaContent('meta[name="description"]', 'name', 'description', description);
      setMetaContent('meta[property="og:description"]', 'property', 'og:description', description);
    }
    if (title) {
      setMetaContent('meta[property="og:title"]', 'property', 'og:title', title);
    }
    setLinkHref('canonical', canonical);
    setMetaContent('meta[property="og:url"]', 'property', 'og:url', canonical);
    setMetaContent('meta[property="og:image"]', 'property', 'og:image', ogImage);
  }, [title, description, path, image]);
}

export default usePageSeo;

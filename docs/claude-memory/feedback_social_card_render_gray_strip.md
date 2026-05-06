---
name: Social launch cards have gallery-view gray body — strip before single-card render
description: Rendering individual cards from social-launch-cards-v2.html requires CSS overrides on body/html or the screenshot has gray top/bottom strips
type: feedback
originSessionId: c3d0833d-cb3f-474f-8dd8-e530f3300c60
---
When rendering individual cards from `design/brand/social-launch-cards-v2.html` (or its successors) to PNG, the source HTML's `<body>` is styled for gallery preview:

```css
body { background: #999; display: flex; flex-wrap: wrap; gap: 40px; padding: 40px; justify-content: center; }
```

That `#999` background and `40px` padding leak into screenshots when one card is rendered alone, producing gray strips at the top and bottom of the PNG.

**Why:** The user spotted this immediately — gray bleed is visually obvious and ruins the editorial paper-on-paper aesthetic.

**How to apply:** Any future renderer (e.g., `/tmp/render_launch_cards.py` or a permanent script) must inject an override stylesheet into the per-card HTML before invoking headless Chrome. Example:

```html
<style>
  html, body { background: transparent !important; padding: 0 !important; margin: 0 !important; gap: 0 !important; }
  .card { margin: 0 !important; }
</style>
```

Verify after rendering by reading the PNG — the card edge (1080×1350) should be flush with the paper background, no gray strip top or bottom. If you ever see a gray strip in a card preview, the override didn't apply.

Same caution applies to any future card source HTML that uses a gallery layout — check the body styling before rendering.

**Second gotcha — card extraction:** A naive regex like `<div class="card">.*?</div>\s*</div>\s*</div>` will silently truncate cards with deeply nested divs (stats grids, pillar lists). The 3rd-from-last `</div>` may match the closing of a nested element rather than the card itself, dropping the footer (RigaCap brand + CTA) entirely from the rendered PNG. Use a depth-counting extractor that walks `<div`/`</div>` and matches at depth=0, not regex.

**Third tip:** before considering the render done, scan rows of the PNG for non-paper pixels and confirm content extends to ~y=1289 (just above the 60px content padding-bottom). If content stops at y=1257 or earlier on a 1350-tall card, the footer is missing.

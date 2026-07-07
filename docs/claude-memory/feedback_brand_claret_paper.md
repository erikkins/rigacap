---
name: feedback-brand-claret-paper
description: "BRAND = claret + paper (editorial). NEVER navy/gold — that's the retired old brand."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

Erik (Jul 2 2026): **"navy gold brand is the OLD design… make a note so we never use navy and gold again."**

**The RigaCap brand is CLARET + PAPER — an editorial, warm, "old-money / capital-preservation" look. Navy + gold is RETIRED. Do NOT use navy/gold for any new graphic, HTML, PDF, card, or doc.**

**Exact tokens (source of truth: `frontend/tailwind.config.js`):**
- paper: `#F5F1E8` (default bg) · deep `#EDE7D8` · card `#FAF7F0`
- ink: `#141210` (text) · mute `#5A544E` · light `#8A8279`
- claret: `#7A2430` (primary accent) · light `#9A3444`
- rule (borders): `#DDD5C7` · dark `#C9BFAC`
- positive/green `#2D5F3F` · negative/red `#8F2D3D`

**Fonts:** display/headlines = **Fraunces** (serif, Georgia fallback); body = **IBM Plex Sans**; mono = IBM Plex Mono. (Google Fonts import; when rendering HTML→PNG/PDF via headless Chrome add `--virtual-time-budget=3000` so the web fonts load first.)

**How to apply:** every new brand asset (product one-pagers, social cards, investor/report HTML, decks) uses this palette + Fraunces/IBM Plex. Good reference implementation: `design/documents/rigacap-2tier-product-overview.html` (Jul 2). NOTE: older docs (`rigacap-investor-report.html`, `social-launch-cards*.html`, etc.) may still carry the OLD navy/gold — regenerate them in claret/paper if touched. Related: [[project_preserver_2tier_phase2]].

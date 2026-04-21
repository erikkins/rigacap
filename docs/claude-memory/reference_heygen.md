---
name: HeyGen avatar IDs, voice, and API notes
description: Erik's 8 HeyGen avatar IDs (2 landscape, 6 portrait) + voice ID + v3 API limitations
type: reference
originSessionId: 39ce1e26-1ab7-4fbd-8e9a-6c892d933b00
---
- **Avatar IDs — LANDSCAPE (use aspect_ratio 16:9):**
  - `ac84b8d9349340278a69cbcae5db15bc`
  - `bc69ba83f80249c8a7c7df9a0d97bdff` (original default)
- **Avatar IDs — PORTRAIT (use aspect_ratio 9:16):**
  - `34b5e03e3d5d4b3bbfaf0fe5e817348b`
  - `2e4229526c294b8c92804dffcb9f5070`
  - `79d9f095a2d74071b4026064093563dd`
  - `3b9df741f65c4e178aec1a057ef7fab2`
  - `89dc1faa445048bea66aaec387ace7a0`
  - `9e2730b9a3da4e38bcf5d857fd15e503`
- **Voice ID:** `99dd0e4a4ace44c39f8c0a79d0bd42dd`
- **Base Avatar ID:** `cfe14f503dff46478bc38b146e3e0799` (don't use directly)
- **API:** Use v3 endpoint (`POST https://api.heygen.com/v3/videos`). v2 produces low bitrate.
- **CRITICAL: Aspect ratio must match avatar orientation** — portrait avatars in 16:9 get head cropped. Landscape in 9:16 also breaks.
- **KNOWN ISSUE: API lip sync is worse than website.** Website uses Avatar V motion engine; API appears stuck on Avatar IV. No documented param to force V. `avatar_engine`, `scale`, `test`, `avatar_style` are all silently ignored by v3. Raise with HeyGen support.
- **v3 accepts only these params:** type, avatar_id, title, resolution, aspect_ratio, background, remove_background, callback_url, callback_id, output_format, script, voice_id, audio_url, audio_asset_id, voice_settings, motion_prompt, expressiveness
- **Env var:** `HEYGEN_AVATAR_ROTATION` = comma-separated list of all 8 IDs

Updated Apr 20, 2026.

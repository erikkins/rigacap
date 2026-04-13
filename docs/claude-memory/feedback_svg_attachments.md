---
name: Never let raw SVG bytes flow back into conversation
description: SVGs returned as image attachments cause Anthropic API 400 loops — always pre-convert to PNG before referencing
type: feedback
originSessionId: 39ce1e26-1ab7-4fbd-8e9a-6c892d933b00
---
When working with SVG files, never let the raw SVG content come back into the conversation as an image attachment. Anthropic's vision API only accepts PNG/JPEG/GIF/WebP — SVG triggers `"Could not process image"` (HTTP 400), and because the bad attachment stays in the conversation history, every subsequent turn re-sends it and 400s again. Session becomes unrecoverable; only `--resume` to a clean point or starting fresh fixes it.

**Why:** Lost a major session (`7dc69abd-ade1-4ef8-b901-42d3cee7df53`, Apr 13 2026) to this exact loop. We were updating `drawLogo` in `design/brand/social-launch-cards.html` to swap the old Deco Streamline tower for the new `icon-halo.svg`. A Bash command that base64-encoded the SVG returned the blob inline, the API treated it as an image attachment, and the 400 loop began. ~10 turns of "try again" / "now?" / "still" all 400'd before we abandoned the session.

**How to apply:**
- Before referencing an SVG anywhere downstream (canvas drawing, headless Chrome render, image embed), pre-convert to PNG: `chrome --headless --screenshot=output.png --window-size=W,H file:///path/to/wrapper.html` where wrapper.html does `<img src="file:///path/to/icon.svg">`.
- When reading SVG content with the Read tool, that's safe (returned as text). Risk is only when SVG content is sent as an attachment/image part.
- Avoid `cat file.svg` or scripts that print SVG content — they may trigger image-attachment parsing depending on terminal output handling.
- If a 400 loop starts, abandon the session immediately. Don't keep retrying — start fresh with a clean conversation.

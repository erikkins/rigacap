---
name: feedback-checkpoint-memory-during-session
description: "Checkpoint working state to a memory file at each breakpoint — abrupt VS Code close kills the process, no shutdown hook can save context"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 2dce3134-d861-45c4-a371-80378750f8c0
---

Erik lost a good chunk of working context on Jun 25 2026 when he accidentally closed VS Code mid-session. The live context window was gone; only the on-disk transcript (`701a2e93-…jsonl`) survived, and it had to be mined to reconstruct the active task.

**Why:** there is no reliable "right before shutdown" moment Claude can act in. Closing VS Code kills the process — by then the model isn't running. The closest hook (`SessionEnd`) runs a shell script only (can't summarize intelligently) and may not even fire on a hard window-close. So shutdown-time auto-save is impossible.

**How to apply:** checkpoint *during* the session, not at the end. At each meaningful breakpoint in any multi-step build, write/update the relevant `project_*` memory file with current state + next steps. Then a surprise close costs at most the last chunk, never the whole session. This is exactly what the `RESUME …` / `LOOP CLOSED …` index entries already are — keep doing it proactively, without being asked. Recovery path when context IS lost: transcripts live at `~/.claude/projects/-Users-erikkins-CODE-stocker-app/*.jsonl`; resume a specific one with `claude --resume` (NOT `--continue`, which only reloads the most-recent session). See [[project_admin_mobile_app_jun25]] for the recovery that prompted this.

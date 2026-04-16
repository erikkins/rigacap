---
name: NEVER commit secrets, passwords, or credentials to git
description: Absolute red line. Any file containing a real password, DB URI with creds, API key, JWT secret, or Stripe/Anthropic/AWS credential must never be `git add`-ed. Scan diffs for creds before any commit.
type: feedback
originSessionId: 39ce1e26-1ab7-4fbd-8e9a-6c892d933b00
---
Absolute rule: **nothing with a live credential ever enters a git commit.** Applies to scripts, configs, notebooks, migration files, fixtures, anything.

**Why:** Apr 16 2026 I committed `scripts/local_wf_runner.py` without reading its contents. It contained the RDS master password hardcoded at line 105. GitGuardian flagged it within ~30 min. Triggered a full incident: stop running jobs, rotate the RDS password, update two Lambdas' env vars, refactor 6+ scripts that had the same hardcoded URI. RDS is publicly accessible (0.0.0.0/0 on 5432), so the blast radius of a leaked master password is full DB compromise: user emails, bcrypt hashes, Stripe customer IDs.

**How to apply:**

1. **Before every `git add`** on a file I haven't read recently, `grep -E "password|api.key|secret|postgresql://|postgres://|mongodb://|AKIA[A-Z0-9]|sk-ant|sk-live|sk_live|whsec_"` the file. Any hit → stop, fix, re-scan.
2. **Never `git add .` or `git add -A`** — always add specific paths. The blast-radius of a reflex `git add .` is why this happened.
3. **Scripts that need DB access** must read `os.environ['DATABASE_URL']` — never a hardcoded fallback with real creds. If the env var is missing, raise a helpful error, don't fall back to a real URI.
4. **Keep a repo-root `.env`** (gitignored) for local dev. Scripts source it.
5. **The `scripts/*.py` files Erik has locally** (param_tournament.py, test_rs_leaders.py, tournament_7dates.py, tpe_megacap_2023.py, tpe_optimizer.py) still had the old password as of Apr 16. They were UNTRACKED, not yet committed — but one `git add scripts/` would have pushed all of them. Before committing anything from `scripts/`, audit each file for hardcoded URIs.
6. **When writing new scripts or receiving code from an agent**, read it end-to-end BEFORE staging. Pattern-match for credential shapes.
7. **If a secret does leak**, rotate the credential within minutes — not hours. Longer window = more exploitation risk.

**Credentials that have ever been hardcoded in this repo (all must be considered burnt):**
- The pre-Apr-16 RDS master password starting with `6NgvDXGyc2Gk...`. Rotated Apr 16 2026.

**Long-term hardening to advocate for:**
- Repo-level pre-commit hook (`detect-secrets`, `gitleaks`, or trufflehog) that blocks commits containing credential-shaped strings.
- GitHub Actions secret-scan on every push (GitHub has native secret scanning; enable it if not already).
- Move RDS off public-IP to VPC-only; local scripts connect through Session Manager/SSH tunnel. That way even a leaked password doesn't grant network access.

#!/bin/bash
# Sync Claude Code memory files into the repo for git versioning.
# Runs via cron every 30 minutes. Only commits if there are actual changes.

set -euo pipefail

REPO_DIR="/Users/erikkins/CODE/stocker-app"
MEMORY_SRC="$HOME/.claude/projects/-Users-erikkins-CODE-stocker-app/memory"
MEMORY_DEST="$REPO_DIR/docs/claude-memory"

# Bail if source doesn't exist
if [ ! -d "$MEMORY_SRC" ]; then
    echo "$(date): Memory source not found: $MEMORY_SRC"
    exit 0
fi

# Create destination if needed
mkdir -p "$MEMORY_DEST"

# Sync files (mirror, delete removed files)
rsync -a --delete "$MEMORY_SRC/" "$MEMORY_DEST/"

# Check if anything changed
cd "$REPO_DIR"
if git diff --quiet -- docs/claude-memory/ && \
   [ -z "$(git ls-files --others --exclude-standard -- docs/claude-memory/)" ]; then
    # No changes
    exit 0
fi

# Stage and commit
git add docs/claude-memory/
git commit -m "$(cat <<'EOF'
Auto-snapshot Claude memory files

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"

echo "$(date): Memory snapshot committed"

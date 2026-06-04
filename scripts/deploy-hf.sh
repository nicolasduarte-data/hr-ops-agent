#!/usr/bin/env bash
#
# deploy-hf.sh — push the current `master` tree to Hugging Face Spaces.
#
# WHY THIS EXISTS
# ---------------
# `origin/master` history contains a binary blob (docs/screenshots/langfuse-trace.png,
# added then removed). HF Spaces' pre-receive hook scans every object in the pushed
# range and REJECTS that blob — even though it's deleted at HEAD. So a plain
# `git push huggingface master` fails with a non-fast-forward / binary-rejected error,
# and the two remotes have permanently divergent histories.
#
# This script sidesteps it cleanly: it creates a single new commit whose *tree* is
# exactly master's current tree (which no longer tracks the PNG), parented on HF's
# current master. The only objects pushed are that commit plus any blobs in master's
# tree not already on HF — the PNG is in neither, so the hook passes.
#
# No history rewrite on origin (origin keeps the PNG so the README's raw-GitHub image
# URL still resolves). No manual clean-branch dance.
#
# USAGE
#   bash scripts/deploy-hf.sh
#
# PRECONDITIONS
#   - You've already pushed your changes to origin/master.
#   - A `huggingface` remote exists (the Space's git URL).
#
set -euo pipefail

REMOTE="huggingface"
SOURCE_REF="master"

# 1. Sanity: the huggingface remote must exist.
if ! git remote get-url "$REMOTE" >/dev/null 2>&1; then
  echo "ERROR: no '$REMOTE' remote configured. Add it with:"
  echo "  git remote add $REMOTE https://huggingface.co/spaces/<user>/<space>"
  exit 1
fi

# 2. Refuse to deploy a dirty tree — what you push should be what's committed.
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "ERROR: working tree has uncommitted changes. Commit or stash first."
  exit 1
fi

# 3. Fetch HF's current master to parent the new commit on it.
echo "Fetching $REMOTE…"
git fetch "$REMOTE" --quiet

# 4. Build a commit whose tree == master's tree, parented on HF master.
TStamp="$(date -u +%Y-%m-%dT%H:%MZ)"
NEW_COMMIT="$(git commit-tree "${SOURCE_REF}^{tree}" \
  -p "${REMOTE}/master" \
  -m "deploy: sync ${SOURCE_REF} tree → HF Spaces (${TStamp})")"

# 5. Push it as HF master.
echo "Pushing ${SOURCE_REF} tree → ${REMOTE}/master …"
git push "$REMOTE" "${NEW_COMMIT}:master"

echo "✓ Deployed ${SOURCE_REF} → ${REMOTE}/master (${NEW_COMMIT})."
echo "  HF Spaces will now rebuild. Watch the Space logs for the build."

#!/usr/bin/env bash
# -----------------------------------------------------------------------------------------------
# init-project.sh — rebrand this template for a new engagement in one command.
#
#   scripts/init-project.sh <slug> ["Display Name"] [--dry-run]
#
#   <slug>  lowercase letters/digits, 2-20 chars, starting with a letter (valid as a Python package,
#           DNS label, Helm release, image name and env-var prefix), e.g. "acme" or "contoso"
#
# Renames:  python package golden -> <slug>, CLI `golden` -> `<slug>`, GOLDEN_* env -> <SLUG>_*,
#           golden_* metrics -> <slug>_*, images/charts/namespaces golden-* -> <slug>-*,
#           "Golden Platform" -> "<Display Name>". Author byline/copyright is preserved.
# -----------------------------------------------------------------------------------------------
set -euo pipefail

usage() { sed -n '3,14p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

[[ $# -ge 1 ]] || usage 1
SLUG="$1"; shift
DISPLAY="$(printf %s "${SLUG:0:1}" | tr "[:lower:]" "[:upper:]")${SLUG:1} Platform"
DRY_RUN=false
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    -h|--help) usage 0 ;;
    *) DISPLAY="$arg" ;;
  esac
done

if [[ ! "$SLUG" =~ ^[a-z][a-z0-9]{1,19}$ ]]; then
  echo "error: slug must match ^[a-z][a-z0-9]{1,19}\$ (got '$SLUG')" >&2
  exit 2
fi
if [[ "$SLUG" == "golden" ]]; then
  echo "nothing to do: slug is already 'golden'"; exit 0
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[[ -d src/golden ]] || { echo "error: src/golden not found — already initialised?" >&2; exit 1; }
if [[ -n "$(git status --porcelain 2>/dev/null || true)" ]] && [[ "$DRY_RUN" == false ]]; then
  echo "error: working tree is dirty; commit or stash first so the rename is reviewable" >&2
  exit 1
fi

UPPER="$(printf %s "$SLUG" | tr "[:lower:]" "[:upper:]")"

# Text files tracked by git, excluding lockfiles, binaries and generated protobuf code.
FILES=()
while IFS= read -r f; do FILES+=("$f"); done < <(
  git ls-files | grep -Ev '(package-lock\.json|\.png|\.jpg|\.ico|\.pdf|/generated/.*_pb2\.py)$' || true
)

echo "Renaming golden -> $SLUG  ('Golden Platform' -> '$DISPLAY') across ${#FILES[@]} files"
if [[ "$DRY_RUN" == true ]]; then
  grep -l -E 'golden|GOLDEN|Golden Platform' "${FILES[@]}" 2>/dev/null | sed 's/^/  would edit: /' || true
  echo "  would move: src/golden -> src/$SLUG"
  exit 0
fi

export SLUG UPPER DISPLAY
for f in "${FILES[@]}"; do
  [[ -f "$f" ]] || continue
  grep -q -E 'golden|GOLDEN|Golden Platform' "$f" || continue
  perl -pi -e '
    s/Golden Platform/$ENV{DISPLAY}/g;
    s/\bGOLDEN_/$ENV{UPPER}_/g;
    s/\bgolden_/$ENV{SLUG}_/g;
    s/\bgolden\b/$ENV{SLUG}/g;
  ' "$f"
done

git mv src/golden "src/$SLUG"
if [[ -d deploy/helm/golden ]]; then git mv deploy/helm/golden "deploy/helm/$SLUG"; fi
for dash in observability/grafana/dashboards/golden-*.json; do
  [[ -e "$dash" ]] || continue
  git mv "$dash" "${dash/golden-/$SLUG-}"
done

cat <<EOF

Done. Next steps:
  1. Review:   git diff --stat && git diff
  2. Reinstall: python -m pip install -e '.[dev]'
  3. Verify:   make lint test
  4. Edit platform.yaml (cloud, region, domains, AI-safety mode), then: make up / make deploy
EOF

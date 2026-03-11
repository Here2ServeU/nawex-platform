#!/usr/bin/env bash
set -euo pipefail

# Enforce canonical-first naming for newly added files while keeping legacy paths intact.
failures=0

suggest_canonical() {
  local path="$1"
  case "$path" in
    docs/01-executive/*) echo "docs/executive/" ;;
    docs/02-architecture/*) echo "docs/architecture/" ;;
    docs/03-compliance/*) echo "docs/compliance/" ;;
    docs/04-product/*) echo "docs/product/" ;;
    docs/05-operations/*) echo "docs/operations/" ;;
    ai/features/*) echo "ai/feature_engineering/" ;;
    platform/event-processing/*) echo "platform/event_streams/" ;;
    platform/resilience-engine/*) echo "platform/resilience_engine/" ;;
    platform/notification-engine/*) echo "platform/notification_system/" ;;
    fintech/transaction-engine/*) echo "fintech/transaction_engine/" ;;
    fintech/fraud-detection/*) echo "fintech/fraud_detection/" ;;
    healthcare/ehr-ingestion/*) echo "healthcare/ehr_ingestion/" ;;
    healthcare/clinical-decision-support/*) echo "healthcare/clinical_monitoring/" ;;
    sre/slis-slos/*) echo "sre/slis_slos/" ;;
    sre/chaos/*) echo "sre/chaos_testing/" ;;
    *) echo "<canonical path>" ;;
  esac
}

is_legacy_path() {
  local path="$1"
  case "$path" in
    docs/01-executive/*|docs/02-architecture/*|docs/03-compliance/*|docs/04-product/*|docs/05-operations/*) return 0 ;;
    ai/features/*) return 0 ;;
    platform/event-processing/*|platform/resilience-engine/*|platform/notification-engine/*) return 0 ;;
    fintech/transaction-engine/*|fintech/fraud-detection/*) return 0 ;;
    healthcare/ehr-ingestion/*|healthcare/clinical-decision-support/*) return 0 ;;
    sre/slis-slos/*|sre/chaos/*) return 0 ;;
    *) return 1 ;;
  esac
}

resolve_range() {
  if [[ -n "${GITHUB_BASE_REF:-}" ]]; then
    if git rev-parse --verify "origin/${GITHUB_BASE_REF}" >/dev/null 2>&1; then
      local base
      base="$(git merge-base HEAD "origin/${GITHUB_BASE_REF}")"
      echo "${base}...HEAD"
      return 0
    fi
  fi

  if git rev-parse --verify HEAD~1 >/dev/null 2>&1; then
    echo "HEAD~1...HEAD"
    return 0
  fi

  return 1
}

main() {
  local range
  if ! range="$(resolve_range)"; then
    echo "[canonical-check] Could not determine comparison range. Skipping check."
    exit 0
  fi

  echo "[canonical-check] Checking newly added files in range: ${range}"

  local added
  added="$(git diff --name-only --diff-filter=A "${range}" || true)"

  if [[ -z "${added}" ]]; then
    echo "[canonical-check] No newly added files found."
    exit 0
  fi

  while IFS= read -r file; do
    [[ -z "${file}" ]] && continue
    if is_legacy_path "${file}"; then
      echo "[canonical-check] New file in legacy path: ${file}"
      echo "[canonical-check] Use canonical path instead: $(suggest_canonical "${file}")"
      failures=$((failures + 1))
    fi
  done <<< "${added}"

  if [[ ${failures} -gt 0 ]]; then
    echo "[canonical-check] Found ${failures} canonical path policy violation(s)."
    exit 1
  fi

  echo "[canonical-check] Passed."
}

main "$@"

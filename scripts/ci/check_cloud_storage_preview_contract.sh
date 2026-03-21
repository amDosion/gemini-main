#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if ! command -v npm >/dev/null 2>&1; then
  echo "[error] npm is required for check_cloud_storage_preview_contract.sh" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "[error] python3 is required for check_cloud_storage_preview_contract.sh" >&2
  exit 1
fi

KEY_TEST_FILES=(
  "frontend/components/views/cloudStorage/useXhrImagePreview.test.tsx"
  "frontend/components/views/cloudStorage/useCloudStorageViewer.test.tsx"
  "backend/tests/test_storage_preview_proxy_contract.py"
)

for test_file in "${KEY_TEST_FILES[@]}"; do
  if [[ ! -f "$test_file" ]]; then
    echo "[error] missing Cloud Storage preview contract test file: $test_file" >&2
    exit 1
  fi
done

echo "[check] Cloud Storage preview frontend regression gate"
npm run test -- \
  frontend/components/views/cloudStorage/useXhrImagePreview.test.tsx \
  frontend/components/views/cloudStorage/useCloudStorageViewer.test.tsx \
  --environment jsdom

echo "[check] Cloud Storage preview build gate"
npm run build

echo "[check] Cloud Storage preview backend contract gate"
(
  cd backend
  PYTHONPATH=. python3 -m pytest \
    tests/test_storage_preview_proxy_contract.py \
    -q
)

echo "[ok] Cloud Storage preview contract gate passed"

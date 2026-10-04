#!/bin/bash
# Clone the UE source onto the VM at the tag the clients use, and stamp its version.
# Needs: this machine's SSH key loaded in ssh-agent (ssh-add -l) and its GitHub account
# linked to an Epic account. The key is forwarded, never copied to the VM.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/config.sh"

ssh-add -l >/dev/null || { echo "No key in ssh-agent; run ssh-add first." >&2; exit 1; }
git ls-remote --tags "$OW_ENGINE_REPO" "$OW_ENGINE_TAG" | grep -q . \
  || { echo "Cannot see $OW_ENGINE_TAG in $OW_ENGINE_REPO (is GitHub linked to Epic?)" >&2; exit 1; }

ow_ensure_running
ow_ssh -- -A "set -e
sudo chown -R \$(id -un):\$(id -gn) $OW_REMOTE_ROOT
mkdir -p ~/.ssh
grep -q github.com ~/.ssh/known_hosts 2>/dev/null || ssh-keyscan -t ed25519 github.com >> ~/.ssh/known_hosts 2>/dev/null
cd $OW_REMOTE_ENGINE
if [ ! -d .git ]; then
  git clone --depth 1 --branch $OW_ENGINE_TAG --single-branch $OW_ENGINE_REPO . 2>&1 | tail -2
fi
# A source checkout stamps itself changelist 0; give it the launcher build's stamp.
python3 - <<PY
import json
p = 'Engine/Build/Build.version'
d = json.load(open(p))
d['Changelist'] = $OW_ENGINE_CHANGELIST
d['BranchName'] = '$OW_ENGINE_BRANCH'
json.dump(d, open(p, 'w'), indent='\t')
print(open(p).read())
PY
git describe --tags; df -h / | tail -1"
echo "Cloned. The VM is still running: run engine_build.sh next, or vm.sh stop."

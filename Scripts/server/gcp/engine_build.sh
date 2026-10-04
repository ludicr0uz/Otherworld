#!/bin/bash
# Start the engine build on the VM, detached (tmux session "build"). The VM powers itself
# off when the build ends, pass or fail; read the result with: vm.sh status
# Safe to rerun after a spot preemption: the build resumes where it stopped.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/config.sh"

ow_ensure_running
gcloud compute scp "$HERE/remote/build_engine.sh" "$OW_VM:/tmp/build_engine.sh" \
  --project "$OW_PROJECT" --zone "$OW_ZONE" --quiet
ow_ssh --command "set -e
test -d $OW_REMOTE_ENGINE/.git || { echo 'No engine source; run engine_clone.sh first.' >&2; exit 1; }
if tmux has-session -t build 2>/dev/null; then echo 'A build is already running.'; exit 0; fi
install -m 0755 /tmp/build_engine.sh $OW_REMOTE_ROOT/build_engine.sh
tmux new-session -d -s build '${NO_SHUTDOWN:+NO_SHUTDOWN=1 }$OW_REMOTE_ROOT/build_engine.sh'
sleep 5; cat $OW_REMOTE_OUT/engine-build.status"

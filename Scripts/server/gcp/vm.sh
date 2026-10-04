#!/bin/bash
# Day-to-day control of the build VM: vm.sh start | stop | ssh | status
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/config.sh"

case "${1:-status}" in
  start) ow_ensure_running; echo "$OW_VM is running. Stop it when done: it bills by the hour." ;;
  stop)  gcloud compute instances stop "$OW_VM" --project "$OW_PROJECT" --zone "$OW_ZONE" ;;
  ssh)   shift; ow_ssh "$@" ;;
  status)
    state="$(ow_state)"
    echo "$OW_VM: ${state:-does not exist}"
    # The build's status file is on the VM's disk, so it can only be read while it runs.
    if [ "$state" = RUNNING ]; then
      ow_ssh --command "cat $OW_REMOTE_OUT/engine-build.status 2>/dev/null || echo 'no build run yet'
tmux has-session -t build 2>/dev/null && echo 'build session: running' || echo 'build session: none'
tail -c 4000 $OW_REMOTE_OUT/engine-build.log 2>/dev/null | tr '\r' '\n' | tail -4
df -h / | tail -1"
    fi ;;
  *) echo "usage: vm.sh start|stop|ssh|status" >&2; exit 2 ;;
esac

#!/bin/bash
# Shared settings for the GCP build VM scripts. Sourced, never run.
# Override any of these from the environment, e.g. OW_ZONE=us-east4-a ./vm_create.sh

# dev-team sessions set OW_NO_GCP=1: these scripts spend money and are the owner's to run.
if [ "${OW_NO_GCP:-0}" = 1 ]; then
  echo "GCP is disabled in this session (OW_NO_GCP=1)." >&2
  exit 3
fi

OW_PROJECT="${OW_PROJECT:-play-history-service}"
OW_ZONE="${OW_ZONE:-us-central1-a}"
OW_VM="${OW_VM:-otherworld-build}"

# The project's CPUS_ALL_REGIONS quota is 32 with 2 in use, so 30 vCPUs is the ceiling.
OW_MACHINE_TYPE="${OW_MACHINE_TYPE:-n2-custom-30-65536}"
OW_DISK_SIZE="${OW_DISK_SIZE:-300GB}"
# pd-ssd is fastest; pd-balanced is cheaper. The type cannot be changed in place.
OW_DISK_TYPE="${OW_DISK_TYPE:-pd-ssd}"
OW_IMAGE_FAMILY="${OW_IMAGE_FAMILY:-ubuntu-2204-lts}"
OW_IMAGE_PROJECT="${OW_IMAGE_PROJECT:-ubuntu-os-cloud}"

# Must match the engine the clients are built with:
# "/Users/Shared/Epic Games/UE_5.8/Engine/Build/Build.version".
OW_ENGINE_TAG="${OW_ENGINE_TAG:-5.8.3-release}"
OW_ENGINE_CHANGELIST="${OW_ENGINE_CHANGELIST:-58210709}"
OW_ENGINE_BRANCH="${OW_ENGINE_BRANCH:-++UE5+Release-5.8}"
OW_ENGINE_REPO="${OW_ENGINE_REPO:-git@github.com:EpicGames/UnrealEngine.git}"

# Layout on the VM.
OW_REMOTE_ROOT=/opt/otherworld
OW_REMOTE_ENGINE=$OW_REMOTE_ROOT/engine
OW_REMOTE_OUT=$OW_REMOTE_ROOT/out

ow_gcloud() { gcloud "$@" --project "$OW_PROJECT"; }
# ow_ssh [ssh flags --] <command>: run a command on the VM.
ow_ssh() { gcloud compute ssh "$OW_VM" --project "$OW_PROJECT" --zone "$OW_ZONE" --quiet "$@"; }
ow_state() {
  gcloud compute instances describe "$OW_VM" --project "$OW_PROJECT" --zone "$OW_ZONE" \
    --format="value(status)" 2>/dev/null
}
# Start the VM if it is stopped and wait until SSH answers.
ow_ensure_running() {
  if [ "$(ow_state)" != RUNNING ]; then
    gcloud compute instances start "$OW_VM" --project "$OW_PROJECT" --zone "$OW_ZONE"
  fi
  for _ in $(seq 1 30); do
    ow_ssh --command 'true' >/dev/null 2>&1 && return 0
    sleep 10
  done
  echo "VM did not answer SSH" >&2
  return 1
}

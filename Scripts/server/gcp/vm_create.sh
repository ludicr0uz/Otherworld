#!/bin/bash
# Create the build VM and wait for its first-boot install, then stop it.
# Spot, no service account (it cannot reach anything else in the GCP project).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/config.sh"

if [ -n "$(ow_state)" ]; then
  echo "$OW_VM already exists ($(ow_state)). Nothing to do."
  exit 0
fi

gcloud compute instances create "$OW_VM" \
  --project "$OW_PROJECT" --zone "$OW_ZONE" \
  --machine-type "$OW_MACHINE_TYPE" \
  --provisioning-model SPOT --instance-termination-action STOP \
  --image-family "$OW_IMAGE_FAMILY" --image-project "$OW_IMAGE_PROJECT" \
  --boot-disk-size "$OW_DISK_SIZE" --boot-disk-type "$OW_DISK_TYPE" \
  --boot-disk-device-name "$OW_VM" \
  --no-service-account --no-scopes \
  --shielded-secure-boot --shielded-vtpm --shielded-integrity-monitoring \
  --labels game=otherworld,role=build \
  --tags otherworld-build \
  --metadata enable-oslogin=TRUE \
  --metadata-from-file startup-script="$HERE/remote/vm_startup.sh"

echo "Waiting for the first-boot install..."
ow_ensure_running
for _ in $(seq 1 30); do
  ow_ssh --command 'test -f /var/lib/otherworld-build-ready' 2>/dev/null && break
  sleep 15
done
ow_ssh --command 'test -f /var/lib/otherworld-build-ready && sudo chown -R $(id -un):$(id -gn) /opt/otherworld && df -h / | tail -1 && nproc'

if [ "${1:-}" != --keep-running ]; then
  gcloud compute instances stop "$OW_VM" --project "$OW_PROJECT" --zone "$OW_ZONE"
fi

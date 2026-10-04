#!/bin/bash
# Runs on the VM. Builds the UE Linux editor and tools from source, then powers the VM off.
# Rerunnable: every step is incremental. Log and status land in /opt/otherworld/out.
# NO_SHUTDOWN=1 keeps the VM up afterwards.
OUT=/opt/otherworld/out
ENGINE=/opt/otherworld/engine
LOG=$OUT/engine-build.log
STATUS=$OUT/engine-build.status
cd "$ENGINE"
run() {
  echo "=== $(date -u +%FT%TZ) $*" >> "$LOG"
  echo "RUNNING: $*" > "$STATUS"
  "$@" >> "$LOG" 2>&1
}
{
  run ./Setup.sh &&
  run ./GenerateProjectFiles.sh &&
  run Engine/Build/BatchFiles/Linux/Build.sh ShaderCompileWorker Linux Development &&
  run Engine/Build/BatchFiles/Linux/Build.sh UnrealPak Linux Development &&
  run Engine/Build/BatchFiles/Linux/Build.sh UnrealEditor Linux Development &&
  echo "OK $(date -u +%FT%TZ)" > "$STATUS"
} || echo "FAILED at: $(cat "$STATUS") $(date -u +%FT%TZ)" > "$STATUS"
df -h / | tail -1 >> "$LOG"
[ "${NO_SHUTDOWN:-0}" = 1 ] || sudo shutdown -h now

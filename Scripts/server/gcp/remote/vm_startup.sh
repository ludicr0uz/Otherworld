#!/bin/bash
# Runs on the VM as root at every boot; does its work once.
# Installs what a UE source build needs and makes the working folders.
set -euo pipefail
MARK=/var/lib/otherworld-build-ready
[ -f "$MARK" ] && exit 0
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y build-essential git git-lfs rsync unzip zip curl ca-certificates \
  python3 python3-pip pkg-config shared-mime-info xdg-user-dirs tmux htop
mkdir -p /opt/otherworld/engine /opt/otherworld/project /opt/otherworld/out
chmod -R 0777 /opt/otherworld
date -u > "$MARK"

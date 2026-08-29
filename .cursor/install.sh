#!/usr/bin/env bash
#
# Idempotent bootstrap for the po13 Cloud Agent development environment.
#
# The repository hosts multiple independent Python projects on different branches
# (a value-bet scanner at the repo root and a kids-youtube video generator under
# kids-youtube/). This script installs the shared system packages and the union
# of every project's Python dependencies so that a Cloud Agent on any branch is
# ready to run without a separate per-project setup step.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Installing system packages (ffmpeg, fonts, build toolchain)"
sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  ffmpeg \
  fonts-dejavu-core \
  build-essential

echo "==> Installing Python dependencies"
# Installed into the system interpreter (PEP 668 override) so that `python3`
# works out of the box on every branch without activating a virtualenv.
python3 -m pip install --break-system-packages --upgrade pip
python3 -m pip install --break-system-packages -r "${SCRIPT_DIR}/requirements.txt"

echo "==> Environment ready"
python3 --version
ffmpeg -version | head -n 1

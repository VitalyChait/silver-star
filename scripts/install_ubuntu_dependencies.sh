#!/usr/bin/env bash

# Installs Ubuntu system packages required by SilverStar
# - Core Python build/runtime dependencies
# - Audio/TTS runtime (pygame, pyttsx3 fallback)
# - Utilities referenced by scripts (e.g., lsof)
# - espeak-ng as requested
#
# Safe to run multiple times. Requires apt-based Ubuntu/Debian.

set -euo pipefail

if ! command -v apt-get >/dev/null 2>&1; then
  echo "[ERROR] This script requires an apt-based system (Ubuntu/Debian)." >&2
  exit 1
fi

# Use sudo if not root
SUDO=""
if [ "${EUID}" -ne 0 ]; then
  if command -v sudo >/dev/null 2>&1; then
    SUDO="sudo"
  else
    echo "[ERROR] Please run as root or install sudo." >&2
    exit 1
  fi
fi

export DEBIAN_FRONTEND=noninteractive

echo "[INFO] Updating package index..."
$SUDO apt-get update -y

# Core build and Python toolchain
CORE_PKGS=(
  ca-certificates
  curl
  git
  build-essential
  pkg-config
  python3
  python3-venv
  python3-pip
  python3-dev
  libffi-dev
  libssl-dev
  xz-utils
  lsof
  sqlite3
)

# Audio/TTS runtime for pygame + pyttsx3 fallback
# - espeak-ng: engine used by pyttsx3 on Linux
# - ALSA libs and utils: audio backend commonly used by pygame
# - SDL2 + mixer + mpg123: runtime libs to enable mp3 playback via pygame
# - ffmpeg: handy for media handling (not strictly required but useful)
AUDIO_PKGS=(
  espeak-ng
  alsa-utils
  libasound2
  libasound2-data
  libsdl2-2.0-0
  libsdl2-mixer-2.0-0
  libmpg123-0
  ffmpeg
)

echo "[INFO] Installing core packages..."
$SUDO apt-get install -y --no-install-recommends "${CORE_PKGS[@]}"

echo "[INFO] Installing audio/TTS packages..."
$SUDO apt-get install -y --no-install-recommends "${AUDIO_PKGS[@]}"

echo "[INFO] Cleaning up apt caches..."
$SUDO apt-get clean

echo "[SUCCESS] System packages installed. Summary:"
printf "  - Core: %s\n" "${CORE_PKGS[*]}"
printf "  - Audio: %s\n" "${AUDIO_PKGS[*]}"

cat <<'NOTE'

Next steps:
1) Install uv (if not installed):
   curl -LsSf https://astral.sh/uv/install.sh | sh

2) Sync Python deps from backend:
   cd code/backend
   uv sync

3) Optional quick checks:
   - espeak-ng --version        # Verify TTS engine is available
   - python3 -c "import pygame; print('pygame ok')" || true

If audio playback fails in headless or container environments, ensure an ALSA/Pulse backend
is available or run with appropriate audio device bindings.

NOTE


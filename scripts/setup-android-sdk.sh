#!/usr/bin/env bash
set -euo pipefail

SDK_ROOT="${ANDROID_SDK_ROOT:-/opt/android-sdk}"
CMDLINE_TOOLS_ZIP_URL="https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip"

mkdir -p "$SDK_ROOT/cmdline-tools"

if [ ! -x "$SDK_ROOT/cmdline-tools/latest/bin/sdkmanager" ]; then
  tmp_zip="$(mktemp /tmp/cmdline-tools.XXXXXX.zip)"
  wget -q "$CMDLINE_TOOLS_ZIP_URL" -O "$tmp_zip"
  unzip -q -o "$tmp_zip" -d "$SDK_ROOT/cmdline-tools"
  rm -f "$tmp_zip"
  if [ -d "$SDK_ROOT/cmdline-tools/cmdline-tools" ]; then
    rm -rf "$SDK_ROOT/cmdline-tools/latest"
    mv "$SDK_ROOT/cmdline-tools/cmdline-tools" "$SDK_ROOT/cmdline-tools/latest"
  fi
fi

set +o pipefail
yes | "$SDK_ROOT/cmdline-tools/latest/bin/sdkmanager" --sdk_root="$SDK_ROOT" \
  "platform-tools" "platforms;android-34" "build-tools;34.0.0" >/dev/null
set -o pipefail

echo "Android SDK ready at: $SDK_ROOT"

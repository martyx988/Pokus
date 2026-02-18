#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"


# 0) Ensure JDK 17 is available and active (project expects Java 17)
if ! command -v javac >/dev/null || ! javac -version 2>&1 | grep -q '17\.'; then
  apt-get update -y
  DEBIAN_FRONTEND=noninteractive apt-get install -y openjdk-17-jdk-headless
fi
export JAVA_HOME="/usr/lib/jvm/java-17-openjdk-amd64"
export PATH="$JAVA_HOME/bin:$PATH"

# 1) Install Android SDK bits required by this project
"$ROOT_DIR/scripts/setup-android-sdk.sh"

SDK_ROOT="${ANDROID_SDK_ROOT:-/opt/android-sdk}"

# 2) Ensure local.properties points to SDK for Gradle in this container
if [ ! -f "$ROOT_DIR/local.properties" ] || ! grep -q '^sdk.dir=' "$ROOT_DIR/local.properties"; then
  {
    echo "sdk.dir=$SDK_ROOT"
    if [ -f "$ROOT_DIR/gradle.properties" ]; then
      grep -E '^(TWELVE_DATA_API_KEY|ALPHA_VANTAGE_API_KEY)=' "$ROOT_DIR/gradle.properties" || true
    fi
  } > "$ROOT_DIR/local.properties"
fi

# 3) Ensure Gradle wrapper JAR exists; bootstrap it without requiring preinstalled Gradle
if [ ! -f "$ROOT_DIR/gradle/wrapper/gradle-wrapper.jar" ]; then
  GRADLE_VERSION="8.10.2"
  TMP_DIR="$(mktemp -d /tmp/gradle-bootstrap.XXXXXX)"
  DIST_ZIP="$TMP_DIR/gradle-${GRADLE_VERSION}-bin.zip"

  curl -fsSL "https://services.gradle.org/distributions/gradle-${GRADLE_VERSION}-bin.zip" -o "$DIST_ZIP"
  unzip -q "$DIST_ZIP" -d "$TMP_DIR"
  "$TMP_DIR/gradle-${GRADLE_VERSION}/bin/gradle" --no-daemon wrapper --gradle-version "$GRADLE_VERSION"
  rm -rf "$TMP_DIR"
fi

echo "Android build environment ready."

# NYSE Stock Alert Android App

Kotlin + Jetpack Compose Android app that monitors NYSE stocks, stores prices locally, and sends local notifications for user-defined alerts.

## API status and scale concern

The current implementation uses **Alpha Vantage** free tier for:
- symbol search
- 15-minute intraday prices
- full daily historical prices

### Critical limitation

Alpha Vantage free tier does **not** provide one-call full NYSE intraday batch download.
For that reason, the app refreshes only symbols that have active alerts.

See a free-API comparison with pros/cons and recommendation here:
- `docs_API_OPTIONS.md`

## Implemented behavior

- Background refresh every **20 minutes** using WorkManager (retry/backoff + network constraint).
- Worker checks only during NYSE market hours (Mon-Fri, 09:30-16:00 America/New_York).
- Offline caching with Room:
  - `stocks`
  - `daily_prices`
  - `intraday_prices`
  - `alerts`
- Retention:
  - keep historical daily prices up to 10 years
  - keep intraday rows for current trading day only
- Alert types:
  - changes by % from previous reference price
  - drops below
  - rises above
- Optional checkbox: delete alert after trigger.
- Attribution screen included.

## Build prerequisites

- JDK 17 (recommended)
- Android SDK installed with:
  - platform-tools
  - platforms;android-34
  - build-tools;34.0.0

Create `local.properties` with:

```properties
ALPHA_VANTAGE_API_KEY=your_key_here
sdk.dir=/absolute/path/to/android/sdk
```

## Build

```bash
./gradlew assembleDebug
```

## Running on emulator/device

1. Open project in Android Studio.
2. Sync Gradle.
3. Create emulator in Device Manager.
4. Run app.
5. Grant notifications permission.

## About previous PR binary-file error

Some PR tools/reviewers reject binary files in generated PR content. To avoid this, this repo does **not** commit `gradle-wrapper.jar`.
If missing locally, regenerate wrapper with:

```bash
gradle wrapper --gradle-version 8.10.2
```

(Requires local Gradle installation.)

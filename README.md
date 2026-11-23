# PulseTrack

**Train harder. Sync smarter.**

PulseTrack is a native Android fitness, workout logging, and daily activity-tracking application built with **Kotlin** and **Jetpack Compose**. Designed with an offline-first architecture, it combines automatic hardware step counting, a **108+ strength and cardio exercise catalog**, live foreground workout and rest timers, **Epley 1RM** personal record tracking, **Android Health Connect** integration, and real-time **Cloud Firestore** synchronization.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Data Persistence & Cloud Schema](#data-persistence--cloud-schema)
- [Permissions & Hardware Integration](#permissions--hardware-integration)
- [Security & Privacy Safeguards](#security--privacy-safeguards)
- [Getting Started & Build Instructions](#getting-started--build-instructions)
- [Testing](#testing)

---

## Features

### 1. Authentication & Onboarding
- **Google Sign-In** via **Jetpack Credential Manager** (`GetGoogleIdOption` auto-sign-in and `GetSignInWithGoogleOption`) backed by **Firebase Authentication**.
- Guided onboarding to configure **Metric (`kg · km`)** or **Imperial (`lbs · mi`)** units, daily step targets (`3,000–25,000`), and weekly workout goals (`1–7`).

### 2. Today Dashboard & Daily Step Tracking
- **Animated Step Goal Ring** displaying daily steps, remaining distance to goal, active workout minutes, and estimated total calories burned.
- **Hardware Step Sensor (`TYPE_STEP_COUNTER`)**: Reboot-safe and midnight-rollover-aware delta calculation via `StepSensorManager` and `FitnessCalculators.calculateStepSensorDelta`.
- **Manual Step Logging**: Quick `+500` / `+1,000` buttons plus a custom manual step entry sheet.
- **7-Day Interactive Calendar Strip & Active Streak**: Switch between recent days with goal-completion indicators and consecutive active-day streak tracking.

### 3. Strength & Cardio Workout Logger (`108+` Built-In Exercises)
- **108 Built-In Exercises**:
  - **80 Strength Exercises** across 7 muscle groups (`Chest`, `Back`, `Legs`, `Shoulders`, `Arms`, `Core`, `Full Body`).
  - **28 Cardio Exercises** across 8 modalities (`Run`, `Cycle`, `Walk`, `HIIT`, `Swim`, `Row`, `Climb`, `Elliptical`) with exercise-specific MET values.
- **Custom Exercise Creation**: Users can create and save custom strength or cardio exercises scoped to their account.
- **1-Tap Starter Templates**: Quick-launch *Push Day*, *Pull Day*, *Leg Day*, or *5K Run*.
- **Live Timers & Foreground Service**: Drift-free `SystemClock.elapsedRealtime()` workout stopwatch persisted across restarts, backed by `ActiveWorkoutService` (`foregroundServiceType="health"`), plus `60s` / `90s` / `120s` rest countdown presets with vibration feedback.
- **Automatic PR & Tonnage Engine**: Deterministic chronological recalculation of working tonnage and **Epley 1RM** personal records whenever workouts are added, edited, or deleted.

### 4. Progress & Analytics
- Switchable **7D / 30D / 90D** ranges with summary KPIs (`Avg Steps`, `Sessions`, `Volume`).
- Custom Jetpack Compose **Canvas Charts**:
  - **Daily Steps vs. Goal** bar chart with dashed threshold indicator.
  - **Estimated 1RM Progression** line chart per exercise.
  - **Muscle Group Balance** progress bars and **All-Time Personal Records** list.

### 5. Health Connect, Backup & Account Management
- **Two-Way Health Connect Sync**: Reads aggregated daily steps, imports external exercise sessions (with deduplication), and writes logged workouts, calories, and distance.
- **Granular Sync & Display Toggles**: Independent controls for Steps, Workouts, Calories, units, step goals, and Android 12+ Material You dynamic accents.
- **Data Portability & Deletion**: Export workouts as **CSV** or full backups as **JSON** via Android share sheet, or permanently delete account and cloud/local data.

---

## Tech Stack

| Category | Technologies |
|---|---|
| **Language** | Kotlin (JVM 11 target) |
| **UI & Styling** | Jetpack Compose (BOM `2024.09.00`), Material Design 3, Material Icons Extended, Edge-to-Edge, Adaptive `NavigationBar` / `NavigationRail` |
| **Architecture** | MVVM (`ViewModel`, `StateFlow`, `collectAsStateWithLifecycle`), Repository pattern, Kotlin Coroutines & Flow |
| **Navigation** | Navigation Compose (`2.8.9`) |
| **Local Database** | Room (`2.7.0`) with KSP (`2.3.5`) & explicit migrations (`v1 → v2 → v3`) |
| **Preferences** | Jetpack DataStore Preferences (`1.1.7`) |
| **Background Work** | WorkManager (`2.10.0`) periodic & immediate offline-to-cloud sync |
| **Cloud & Auth** | Firebase BoM (`35.1.0`), Firebase Auth, Cloud Firestore (named database), Jetpack Credential Manager (`1.5.0`), Google Identity (`googleid`) |
| **Health & Sensors** | Android Health Connect SDK (`1.1.0`), `SensorManager` (`TYPE_STEP_COUNTER`), `VibratorManager` |
| **Testing** | JUnit 4, Kotlinx Coroutines Test, Robolectric (`4.16.1`), Node.js `@firebase/rules-unit-testing` |
| **Build System** | Gradle (Kotlin DSL), Android Gradle Plugin (`9.1.1`), Version Catalog (`gradle/libs.versions.toml`) |

---

## Architecture

PulseTrack follows an **offline-first MVVM + Repository** architecture:

```
UI Layer (Jetpack Compose Screens + WorkoutLoggerSheet)
        │
        ▼
ViewModel Layer (PulseTrackViewModel, WorkoutLoggerViewModel)
        │
        ▼
Repository Layer (FitnessRepository + FitnessCalculators)
   ├── Local Cache: Room (PulseTrackDatabase / FitnessDao) + DataStore (UserPreferencesStore)
   ├── Remote Sync: FirestoreSyncSource + WorkManager (SyncWorker)
   └── Device APIs: HealthConnectManager + StepSensorManager + ActiveWorkoutService
```

All user mutations write immediately to **Room** and **DataStore** for zero-latency responsiveness, then synchronize to **Cloud Firestore**. Failed or offline writes remain marked `PENDING` / unsynced and are flushed automatically by `SyncWorker` once network connectivity is restored.

---

## Project Structure

```text
.
├── app/
│   ├── build.gradle.kts                  # App Gradle config, dependencies, ProGuard, Secrets plugin
│   ├── google-services.json              # Firebase Android app configuration
│   ├── proguard-rules.pro                # Keep rules for Firestore DTOs, Health Connect, Credential Manager
│   └── src/
│       ├── main/
│       │   ├── AndroidManifest.xml       # Permissions, Health Connect rationale aliases, ActiveWorkoutService
│       │   ├── java/com/example/
│       │   │   ├── PulseTrackApplication.kt       # AppContainer DI & periodic WorkManager sync scheduling
│       │   │   ├── MainActivity.kt                # Auth gate, adaptive NavigationBar/Rail, NavHost
│       │   │   ├── HealthConnectRationaleActivity.kt # Privacy & Health Connect data disclosure screen
│       │   │   ├── data/
│       │   │   │   ├── healthconnect/HealthConnectManager.kt
│       │   │   │   ├── local/
│       │   │   │   │   ├── PulseTrackDatabase.kt  # Room DB v3 + MIGRATION_1_2 & MIGRATION_2_3
│       │   │   │   │   ├── RoomEntities.kt        # DailyMetricEntity, WorkoutEntity, ExerciseSetEntity, CustomExerciseEntity
│       │   │   │   │   └── FitnessDao.kt          # User-scoped Room queries & transactions
│       │   │   │   ├── preferences/UserPreferencesStore.kt # DataStore settings, step baseline, timer snapshot
│       │   │   │   ├── remote/
│       │   │   │   │   ├── FirestoreModels.kt     # @Keep DTOs & FirestorePayloadMapper
│       │   │   │   │   ├── FirestoreSyncSource.kt # Auth-checked Firestore streams & writes
│       │   │   │   │   └── FirestoreErrorHandler.kt # Redacted Firestore diagnostics
│       │   │   │   ├── repository/FitnessRepository.kt
│       │   │   │   ├── sensor/StepSensorManager.kt
│       │   │   │   └── sync/SyncWorker.kt
│       │   │   ├── domain/
│       │   │   │   ├── model/FitnessModels.kt     # 108-exercise catalog, templates, enums, domain models
│       │   │   │   └── util/FitnessCalculators.kt # Epley 1RM, MET burn, step delta, CSV & ID sanitizers
│       │   │   ├── service/ActiveWorkoutService.kt # Health foreground service for active workout timer
│       │   │   └── ui/
│       │   │       ├── auth/                      # AuthHelper, AuthScreen, OnboardingScreen
│       │   │       ├── screens/                   # TodayScreen, WorkoutsScreen, ProgressScreen, HealthSettingsScreen, WorkoutLoggerSheet
│       │   │       ├── theme/                     # Color.kt, Theme.kt, Type.kt
│       │   │       └── viewmodel/                 # PulseTrackViewModel, WorkoutLoggerViewModel
│       │   └── res/
│       │       ├── drawable/                      # Adaptive launcher artwork & workout notification icon
│       │       ├── mipmap-*/                      # Adaptive app launcher icons
│       │       ├── values/                        # strings.xml, colors.xml, themes.xml
│       │       └── xml/                           # backup_rules.xml & data_extraction_rules.xml
│       └── test/java/com/example/
│           ├── PulseTrackQaSuiteTest.kt           # End-to-end catalog, mapper, & security regression tests
│           ├── FitnessCalculatorsTest.kt          # Unit tests for 1RM, pace, units, and sensor deltas
│           ├── ExampleRobolectricTest.kt
│           └── ExampleUnitTest.kt
├── firebase-blueprint.json               # Cloud Firestore entity & collection schema
├── firebase.json                         # Firestore emulator & rules configuration
├── firestore.rules                       # Zero-trust owner-only Firestore security rules
├── firestore.test.js                     # Firestore emulator rules test suite (Node.js)
├── gradle/libs.versions.toml             # Centralized dependency version catalog
├── build.gradle.kts                      # Root Gradle configuration
└── settings.gradle.kts                   # Project module settings (`PulseTrack`)
```

---

## Data Persistence & Cloud Schema

### Cloud Firestore Collections
Configured against a named Firestore database (`R.string.firestore_database_id`) as defined in `firebase-blueprint.json`:
- `/users/{userId}` — Profile display name, email, unit preference (`METRIC` / `IMPERIAL`), step & workout goals, Health Connect toggles, and onboarding status.
- `/users/{userId}/dailyMetrics/{dateKey}` — Per-day (`YYYY-MM-DD`) step counts, manual adjustments, active minutes, calories burned, and daily step goal.
- `/users/{userId}/workouts/{workoutId}` — Workout metadata (`STRENGTH` / `CARDIO`, duration, calories, distance, volume, PR count, notes, source) and up to 100 embedded exercise set maps.

### Local Room Schema (`pulsetrack_offline.db`, Version 3)
- `daily_metrics` (PK: `userId, dateKey`)
- `workouts` (PK: `id`, indexed on `userId, dateKey` and `userId, startedAtMs`)
- `exercise_sets` (PK: `id`, foreign key cascade on `workouts.id`)
- `custom_exercises` (Composite PK: `userId, name`, migrated via `MIGRATION_2_3`)

---

## Permissions & Hardware Integration

Declared in `app/src/main/AndroidManifest.xml`:
- **Network**: `INTERNET`, `ACCESS_NETWORK_STATE`
- **Activity & Background Timer**: `ACTIVITY_RECOGNITION` (runtime requested on Android 10+ / required for Android 14+ `health` foreground service), `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_HEALTH`, `POST_NOTIFICATIONS`, `VIBRATE`
- **Health Connect**: `health.READ_STEPS`, `health.READ_EXERCISE`, `health.WRITE_EXERCISE`, `health.READ_TOTAL_CALORIES_BURNED`, `health.WRITE_TOTAL_CALORIES_BURNED`, `health.READ_DISTANCE`, `health.WRITE_DISTANCE`

---

## Security & Privacy Safeguards

- **Zero-Trust Firestore Rules**: `firestore.rules` denies all access by default and enforces `request.auth.uid == userId`, strict field allowlists, immutable `userId` and `createdAt`, date/ID format validation, and numeric bounds on every write.
- **Cross-Account Local Isolation**: Room DAO queries/deletes filter by `userId`, `custom_exercises` uses a composite `(userId, name)` primary key, Health Connect workout IDs are prefixed per user, and sign-out clears DataStore session state and stops active foreground timer services.
- **CSV Export Hardening**: `FitnessCalculators.sanitizeCsvCell` flattens embedded newlines and neutralizes leading formula characters (`=`, `+`, `-`, `@`, `\t`, `\r`) before quote-escaping.
- **Redacted Error Logging**: `FirestoreErrorHandler` masks UIDs in logged paths, strips user emails and provider metadata, and restricts verbose error details to debug builds.
- **Re-Authentication Guard on Account Deletion**: `HealthSettingsScreen` and `FitnessRepository.deleteAccountAndAllData` verify user ownership and a recent Google Sign-In via Credential Manager before erasing cloud or local data.
- **Backup Exclusions**: `allowBackup="false"` alongside explicit exclusions in `backup_rules.xml` and `data_extraction_rules.xml` prevents Room databases, DataStore preferences, and shared preferences from being included in cloud backups or device-to-device transfers.

---

## Getting Started & Build Instructions

### Prerequisites
- **Android Studio** (Meerkat or newer recommended) with **Android SDK 36** (`minSdk = 26`, `targetSdk = 36`)
- **JDK 11+**
- **Firebase Project** with **Authentication (Google provider enabled)** and **Cloud Firestore** (using the project's `app/google-services.json` and `firestore.rules`)
- *(Optional)* **Node.js** & **Firebase CLI** if running local Firestore rules tests

### Building the App

Using Gradle directly:
```bash
gradle assembleDebug
```

For a release build (uses upload keystore environment variables `KEYSTORE_PATH`, `STORE_PASSWORD`, `KEY_PASSWORD` if configured):
```bash
gradle assembleRelease
```

---

## Testing

### 1. Android JVM Unit & QA Tests
Run the calculator, catalog, schema mapping, and security regression suites:
```bash
gradle :app:testDebugUnitTest --tests com.example.FitnessCalculatorsTest --tests com.example.PulseTrackQaSuiteTest --tests com.example.ExampleUnitTest
```

### 2. Firestore Security Rules Tests
Start the Firestore emulator on port `8085` (per `firebase.json`) and run `firestore.test.js`:
```bash
FIRESTORE_EMULATOR_HOST="127.0.0.1:8085" node --test firestore.test.js
```

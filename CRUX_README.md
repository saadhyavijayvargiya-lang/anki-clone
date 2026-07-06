# Crux

**Exam target: GRE Mathematics Subject Test, point-set topology cluster.**

Crux is a fork of [Anki](https://github.com/ankitects/anki) that turns it from a
memory tool into an exam-readiness tool. It teaches the decision an exam actually
tests, routing a problem to its type and then to the move that solves it, and it
reports three separate, honest scores: Memory, Performance, and Readiness. It
runs on the desktop and on Android (AnkiDroid), sharing Anki's Rust engine.

## License and credit

This is a fork of Anki and is distributed under **AGPL-3.0-or-later**, the same
license as Anki. Credit to **Ankitects Pty Ltd and the Anki contributors** for
Anki, AnkiDroid, and the Anki-Android-Backend. Some parts of Anki are
BSD-3-Clause; those licenses are retained. Crux's additions are AGPL-3.0-or-later.

## What Crux adds (on top of Anki)

- A **Rust engine change**: a points-at-stake triage queue and a three-score
  readiness service (`rslib/src/readiness/`), exposed over protobuf and shared by
  both apps.
- **Three separate scores with ranges and a give-up rule** (see `CRUX_MODELS.md`):
  Memory (FSRS), Performance (Wilson interval over recorded exam attempts), and
  Readiness (a projected GRE Math Subject score, 200 to 990, mapped from topology
  performance). Scores are **withheld** when evidence is insufficient.
- The **Router drill**: a problem-to-type-to-method trainer (active recall on the
  routing decision), with an AI "explain why" that has a deterministic fallback.
- **Cram most dangerous**: a filtered deck of your highest-risk cards plus their
  decision-chain neighbors.
- A redesigned desktop **home dashboard** (scores, coverage/danger heatmap,
  actions) and readiness page, in a consistent visual system.
- **AI** (optional, off by default) via a token-gated Cloudflare proxy so the key
  never ships in the client (see `AI_SETUP.md`).

## Build and run

### Desktop (from source)

Prereqas: the Anki toolchain (Rust pinned by `rust-toolchain.toml`, Python, n2,
and on Windows, msys). Then:

```
tools\ninja.bat pylib qt          # build (Windows; use ./tools/ninja on mac/linux)
```

Run it:

```
set PYTHONPATH=out\qt;qt;out\pylib;pylib
out\pyenv\Scripts\python -c "import aqt; aqt.run()"
```

Crux features are under the **Tools** menu (Readiness, Router drill, Reorder
triage, Cram most dangerous) and on the home dashboard. To package installable
wheels: `tools\build.bat` (outputs to `out\wheels\`).

Optional demo data: with the app closed, `out\pyenv\Scripts\python topgre_eval\seed_demo.py`.

### Mobile (AnkiDroid)

The phone app is the AnkiDroid fork in `Anki-Android/`, built against a custom
backend `.aar` from `Anki-Android-Backend/` that contains the readiness RPCs.

**Download the prebuilt APK** (no build needed) from the
[`topgre-demo-v0.1` release](https://github.com/saadhyavijayvargiya-lang/anki-clone/releases/tag/topgre-demo-v0.1):

- Real phones (arm64): [AnkiDroid-full-arm64-v8a-debug.apk](https://github.com/saadhyavijayvargiya-lang/anki-clone/releases/download/topgre-demo-v0.1/AnkiDroid-full-arm64-v8a-debug.apk)
- Emulator (x86_64): [AnkiDroid-full-x86_64-debug.apk](https://github.com/saadhyavijayvargiya-lang/anki-clone/releases/download/topgre-demo-v0.1/AnkiDroid-full-x86_64-debug.apk)

Install with `adb install <apk>`, or copy the file to the device and open it
(enable "install from unknown sources"). Crux features are in the DeckPicker
overflow menu (TopGRE: Readiness / Cram).

To build it yourself instead:

```
cd Anki-Android-Backend    # build the shared Rust backend into an .aar
cargo run -p build_rust    # needs JAVA_HOME, ANDROID_HOME, ANDROID_NDK_HOME, RELEASE=1
cd ..\Anki-Android
.\gradlew.bat :AnkiDroid:assembleFullDebug
```

APKs land in `Anki-Android\AnkiDroid\build\outputs\apk\full\debug\`
(`...-x86_64-...` for emulators, `...-arm64-v8a-...` for phones). Crux features
are in the DeckPicker overflow menu (TopGRE: Readiness / Cram).

### Sync (desktop <-> phone)

Uses Anki's own sync. Run the local sync server and point both apps at it; see
`SYNC_SETUP.md` for the exact steps and the offline/conflict test.

Both apps run with **AI switched off** and still produce scores.

## Architecture

- **Shared engine (Rust, `rslib/`):** Anki's collection, FSRS scheduler, and
  sync, plus the new `readiness` service. Compiled into the desktop backend and,
  via `Anki-Android-Backend`, into the phone's `.aar`, so the same logic runs on
  both.
- **Protobuf (`proto/anki/readiness.proto`):** the interface for the readiness
  RPCs (points-at-stake queue, get-readiness, record-attempt, most-dangerous,
  performance-eval), generated for Rust, Python, TypeScript, and Kotlin.
- **Desktop UI:** Python/Qt (`qt/aqt/`) plus SvelteKit pages (`ts/routes/`) for
  the readiness dashboard and router drill; the home dashboard is rendered in
  `qt/aqt/deckbrowser.py`. Custom read-only JSON endpoints for the drill/coach/
  heatmap/tuning live in `qt/aqt/mediasrv.py`.
- **Mobile UI:** Kotlin in `Anki-Android/` (DeckPicker readiness + cram).
- **Evaluation (`topgre_eval/`):** leakage check, paraphrase test, benchmark,
  demo seed, and the AI card generator/checker.

## The Rust change (section 7a)

- **What:** a points-at-stake review order (sort by topic weight x student
  weakness / time) and a three-score readiness computation, in
  `rslib/src/readiness/mod.rs` and `service.rs`, with unit tests and a Python
  test (`pylib/tests/test_readiness.py`).
- **Why Rust, not Python:** it reads FSRS memory state, card data, and config
  directly, must run identically on desktop and phone (the shared engine), and
  must stay fast on large decks. In Rust it is written once and ships to both
  platforms; in Python/Kotlin it would be duplicated and would not run on the
  phone's shared backend.
- **Upstream files touched (small, mostly additive; merge risk low to moderate):**
  - additive new modules: `rslib/src/readiness/{mod,service}.rs`,
    `proto/anki/readiness.proto`
  - one-line registrations: `rslib/src/lib.rs`, `rslib/proto/src/lib.rs`,
    `rslib/proto/python.rs`
  - list/enum edits: `qt/aqt/mediasrv.py`, `qt/aqt/webview.py`, `qt/aqt/__init__.py`,
    `qt/aqt/main.py`
  - larger edits (higher merge cost): `qt/aqt/deckbrowser.py` (home dashboard),
    the SCSS palette in `ts/lib/sass/_vars.scss` / `_color-palette.scss`
  - mobile: `Anki-Android/.../DeckPicker.kt`, `res/menu/deck_picker.xml`, and the
    readiness module copied into the `Anki-Android-Backend` submodule.

## More docs

- `CRUX_MODELS.md`: Memory / Performance / Readiness model descriptions + give-up rule.
- `SYNC_SETUP.md`: self-hosted sync server + the offline/conflict test.
- `AI_SETUP.md`: optional AI via the Cloudflare proxy (key stays server-side).
- `CRUX_CHANGELOG.txt`: what changed, newest first.

## Honest status

Solid: the Rust engine change, three honest scores with ranges + give-up rule,
the desktop app, the router drill, and AI (working, with fallback). The
x86_64 phone build runs end to end. In progress / to finish: the arm64 phone
native library, the demonstrated two-way sync test, the study-feature ablation
(interleaving on/off vs plain Anki), memory calibration and performance held-out
write-ups, the benchmark numbers, and the crash/offline tests.

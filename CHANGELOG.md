# Changelog

## v1.1.3

- System-tray menu fully English (`Open main window` / `Exit app`) — the
  first line was hardcoded Chinese in the code and ignored every language
  setting until now.
- Sync-settings tab strip (Notes / Calendar / Album / Recorder) no longer
  overflows its pill.

## v1.1.2

- System-tray menu is now always English (`Open main window` / `Exit app`),
  even on machines whose stored settings still say Chinese.
- Second drives/partitions whose `config.ini` still says
  `LanguageID=2052 / LanguageTag=zh_CN` now open a fully English main window.
- Render, child-window and share-preview windows no longer follow the
  OS/browser language; they stay on en_US.
- Tools → Remote PC is English end to end: password-type screens,
  Skip / Previous / Confirm / Next buttons, `No connection history`, and
  the control-mode descriptions.
- Feature settings → Device connectivity → Mirroring shortcuts →
  `Send messages shortcut` shows
  `Quickly send messages in mirrored QQ and WeChat chats.`
- Fixed a bug where the Phone Mirroring window (`vivoScreen.exe`) opened
  in Chinese instead of English: its embedded default locale is now
  `en-US` (the English resources already shipped inside the app).
- Sync settings tab strip (Notes / Calendar / Album / Recorder) no longer
  overflows its pill: the strip was sized for short Chinese labels and
  `Recorder` hung outside.
- New one-click installer for Windows: the release is a `.rar` containing
  `VivoEnglishPatcher.exe` and the translated `app.asar`. The patcher finds
  the Vivo installation itself (Windows records, then standard folders),
  closes Vivo, backs every original up as `.old`, installs the English
  archive, switches Phone Mirroring to English, sets `config.ini` to
  `1033 / en_US`, and restarts Vivo. A Restore button rolls everything back.
  (The two `.py` sources ship in the repository, not in the release.)

## v1.1.0

### Batch 36 — Broken help images, videos and workers fixed
- **Cause (pre-existing vivo bug, not caused by the translation):** the webpack
  `publicPath` (`X.p`) is never assigned in the shipped bundles, so every
  file-referenced asset resolved to `undefinedimgs/...` and failed to load.
  Only base64-inlined images ever displayed. Asset modules are byte-identical
  between the pristine and translated builds, proving the breakage predates
  this project.
- **Fix:** 458 patches rewriting `X.p+"<asset>"` to the relative
  `"<asset>"` (all host pages live in `dist/electron/*.html`, so relative
  paths resolve). Covers `renderer.js`, `child-window.js`,
  `module-share-preview.js` and other bundles: sync/USB/coordination/screen
  guides, tutorial videos (`.mp4`), web workers and icons.
- All 458 target assets verified present in the archive header before
  patching; full pipeline re-ran green (`node --check`, `verify_asar.py`
  with 2 931 en_US keys / 0 missing, `check_newlines.py`).

### Batch 35 — Remote PC window (vivoControl) translated
- **Cause:** Tools → Remote PC opens a window owned by a **second Electron
  app, `vivoControl`** (`vivoControl/resources/app.asar`), which was never
  covered by the translation pipeline.
- **Fix (`patches_vc.json`, 13 patches + `vc_*` pipeline scripts):** flip the
  default locale `vzh_rCN` → `vus` (vivo's own official English locale,
  already shipped inside the app) in `renderer.js`/`main.js`, switch the
  `isEx` flag so components use `$t("remote.*")` instead of hardcoded
  Chinese, and translate the first-run guide (welcome/tour steps).
- New reproducible pipeline mirroring the main one: `vc_unpack.py`
  (extract) → `vc_apply.py` (apply `patches_vc.json`) → `build_vc_asar.py`
  (rebuild + self-verify) → `vc_verify_installed.py` (marker check).

### Batch 35 — V Claw display name
- `小V Claw` → `V Claw` (4 patches): `window.vclawName` in `renderer.js`,
  `child-window.js`, `module-share-preview.js`, plus the V Claw window title
  in `main.js`. Database queries left untouched on purpose.

## v1.1.0
- Released `app.asar` (354 904 405 bytes): everything below, verified by
  two real-machine installs plus the full static pipeline.
- Remote PC window (`vivoControl`) translated end to end via the new
  `patches_vc.json` pipeline (default locale `vzh_rCN` → vivo's own shipped
  English locale `vus`, `isEx` flag, first-run tour).
- `小V Claw` → `V Claw` display name (4 patches, queries untouched).
- Pre-existing vivo asset bug fixed: 458 `X.p` publicPath patches so help
  images, guide videos, workers and icons actually load (they were broken
  in the pristine build too — asset modules are byte-identical).
- AI-assisted translation disclosed in README (standing rules: logs,
  telemetry, SQL logic and native binaries untouched).

## v1.0.0
- Initial release: full English translation of the main `app.asar`
  (1 135 patches), install guide, screenshots, MIT license for the
  project's own scripts and data.

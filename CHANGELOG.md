# Changelog

## Unreleased

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

## v1.0.0
- Initial release: full English translation of the main `app.asar`
  (1 135 patches), install guide, screenshots, MIT license for the
  project's own scripts and data.

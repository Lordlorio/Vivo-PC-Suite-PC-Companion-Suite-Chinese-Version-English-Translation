# Vivo PC Suite 7.0.5 — English translation

Unofficial English translation of the **Chinese-market version** of Vivo PC Suite 7.0.5
(`vivo办公套件`, the build shipped for phones with a China ROM).

> **Not your version?** If your phone is a global/international model, your PC Suite
> already speaks English — this project targets the CN-ROM desktop app only.

**Unofficial — not affiliated with or endorsed by vivo.**

## Download

Get `app.asar` from the [Releases page](../../releases) (~350 MB).

## Install (Windows)

1. Quit PC Suite completely (tray icon → quit; make sure no `pcsuite` process is left).
2. Open your install folder, by default:
   `C:\Program Files\vivo\pcsuite\resources\`
3. Rename the existing `app.asar` → `app.asar.original` (this is your backup).
4. Copy the downloaded `app.asar` into the same `resources\` folder.
5. Start PC Suite.

**Restore:** quit the app, rename `app.asar.original` back to `app.asar`.

**Notes**
- Applies to **version 7.0.5 (CN installer)** only.
- An official app update will overwrite the translation — just re-apply after updating.
- Run the installer / replace files as administrator if Windows denies access.

## How it works

PC Suite is an **Electron** app: virtually all UI code ships in a single archive,
`resources/app.asar`. The translation:

1. **Unpacks** the archive and translates every hardcoded Chinese string plus the
   `zh_CN` locale files — using the app's own official `en_US` strings as the
   reference wherever they exist (no machine translation).
2. **Fixes layout bits** that break with longer English labels (HTML page titles,
   a few CSS widths).
3. **Filters Chinese values pushed at runtime by vivo's servers.** The app fetches
   a cloud config (`/config/all`) whose Chinese copy (connection dialog, login
   carousel…) *overwrites* the translated local text. Values containing CJK
   characters are now ignored, so the app falls back to the translated strings.
   Functional configs (device models, intervals, images…) are untouched.

Every replacement lives in `patches.json` / `literals.json` as an exact
`original → English` pair with an occurrence count, so the build fails loudly if
anything drifts.

## Build from source

Requirements: **Python 3**, **Node.js**, and your own copy of the untouched
`app.asar` from a 7.0.5 CN install.

```bat
set PC_ASAR_SRC=C:\path\to\app.asar.original
set PC_ASAR_DST=C:\path\to\pcsuite\resources\app.asar

python inject_locales.py
python apply_literals.py --apply
python mk_css_patch.py
python build_asar.py
node --check patched\dist\electron\renderer.js
python verify_asar.py "%PC_ASAR_DST%.new"
python check_newlines.py "%PC_ASAR_DST%.new"
```

Then quit PC Suite and replace `app.asar` with `app.asar.new`.

| Script | Role |
|---|---|
| `inject_locales.py` | Rebuilds `locales-en_US.js.new` (official English locale) |
| `apply_literals.py --apply` | Applies all translations → `patched\` (validation, fails on mismatch) |
| `mk_css_patch.py` | CSS overrides — **must run after** `apply_literals` (it resets `patched\`) |
| `build_asar.py` | Rebuilds the archive → `<PC_ASAR_DST>.new`, self-verifies |
| `verify_asar.py` | Checks en_US key coverage (2 931 keys, 0 missing) |
| `check_newlines.py` | Guards against stray newlines in minified bundles |
| `patches.json`, `literals.json`, `map_en*.json`, `map_files.json`, `skip.json` | The translations themselves |

## Disclaimer

This project only contains translation data and patching tooling written for it.
The attached `app.asar` is a modified copy of vivo's proprietary application,
provided solely so that users who legitimately own the software can run it in
English; all rights to the original application remain with vivo. Use at your own
risk, keep a backup of the original file, and report issues in the tracker.

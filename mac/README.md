# macOS patcher

Translates the **China build** of vivo PC Suite for Mac (`pcsuite.app`,
`com.vivo.pcsuite`) to English using the translation data at the root of this
repository. Tested with **pcsuite 7.0.6 on Apple silicon**.

Keep this folder inside the repository: the script reads `patches.json`,
`literals.json`, `map_en*.json` etc. from `..`.

## Use

```bash
python3 mac/patch_vivo_mac.py              # apply (asks before closing the app)
python3 mac/patch_vivo_mac.py --restore    # put the originals back
python3 mac/patch_vivo_mac.py --dry-run --out /tmp/vivo-en   # build only, install nothing
python3 mac/patch_vivo_mac.py --help
```

Or double-click `Apply English Patch.command` / `Restore Original.command`.
If macOS refuses to open a `.command` file downloaded from the internet, use
**System Settings → Privacy & Security → Open Anyway**, or run the Terminal
command above.

**macOS blocked writing into pcsuite.app:** macOS's App Management protection
stops one app from modifying another. Turn on Terminal (or whichever app runs
the script) under **System Settings → Privacy & Security → App Management**,
reopen it, and run again.

## Installer DMG

```bash
mac/build_dmg.sh 1.0.0    # -> dist/Vivo-English-Patcher-1.0.0-mac.dmg
```

builds the release download: **Vivo English Patcher.app** (compiled from
`installer/Vivo English Patcher.applescript`, universal, ad hoc signed) plus
`Read Me.txt`. The app carries `patch_vivo_mac.py` and the translation data in
`Contents/Resources/patcher` and gives it a native front end: Apply / Restore
dialog, a progress window showing the script's steps, and a pointer to
**App Management** when macOS blocks the write. It runs the script with the
first Python 3.8+ it finds (Homebrew, python.org, or Apple's Command Line Tools,
which it offers to install). It is not notarized, so users allow it once under
**Privacy & Security → Open Anyway**.

## What it changes

| Part | How |
|---|---|
| Main window (`Contents/Resources/app.asar`) | Rebuilt from the installed copy: `map_en*.json` literals, `patches.json`, missing en_US locale keys from `locales-en_US.js.new`, default language zh_CN → en_US (same edits as `build_asar.py`), CSS from `mk_css_patch.py`, TinyMCE `en_US_in.js` |
| Remote PC (`vivoControl/vcontrol.app/.../app.asar`) | `patches_vc.json` |
| `~/Library/Application Support/pcsuite/config.ini` | `LanguageTag=en_US` |
| Phone Mirroring (`vivoScreen.app`) | Only with `--mirror`: the embedded default `zh-CN` → `en-US` (as `patch_vivoscreen_lang.py`). This edits a signed Mach-O, so the app is re-signed ad hoc with its entitlements kept; macOS may ask again for permissions it had granted |

Originals go to `~/Library/Application Support/pcsuite-english-patch/`
(~400 MB) with their SHA-256 in `state.json`. A patched archive carries an
`english-patch-mac.json` marker, so re-running always rebuilds from the
original backup, and after a vivo update the new originals are backed up first.

## Adapting the Windows data to the Mac build

The Mac 7.0.6 bundles are close to Windows 7.0.5 but not identical (other
chunk hashes, locale module ids shifted by 2, some renamed minified
variables), so nothing is copied blindly:

- **`skip.json`** holds Windows byte offsets. Each one is re-located in the
  Mac file: candidate shifts are the Chinese string starts near the original
  offset (and near an estimate from `literals.json` anchors), and the shift
  shared by the most neighbouring skip positions wins. 132/134 are found on 7.0.6.
- **Regions matched by a `patches.json` entry containing Chinese** are left
  untranslated by the literal pass, as on Windows, so the patch can rewrite the
  whole expression afterwards.
- **`patches.json`** entries apply only when the match count equals `expect`.
  When the only difference is a renamed one-letter variable (`e.step` vs
  `t.step`), the match is retried with consistent renames, carried into the
  replacement. On 7.0.6 all 1 636 apply, and all 20 of `patches_vc.json`.
- **`locales-en_US.js.new`** is not copied: its keys are merged into the Mac
  `locales-en_US.js` by namespace (213 keys on 7.0.6).
- CSS fixes are matched by chunk number and only applied when their selector
  exists (5/6 on 7.0.6; the reminder list was restyled).

Every rebuilt archive is read back and checked (contiguous offsets, changed
files byte-exact, integrity hashes), and changed JavaScript is syntax-checked
with `node --check` when Node is installed. Electron's
`EnableEmbeddedAsarIntegrityValidation` fuse is off in 7.0.6; the script
refuses to run if a future build turns it on.

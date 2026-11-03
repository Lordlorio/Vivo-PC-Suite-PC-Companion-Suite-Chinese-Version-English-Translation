#!/bin/bash
# Build dist/Vivo-English-Patcher-<version>-mac.dmg: the double-click
# installer app (mac/installer/*.applescript) carrying patch_vivo_mac.py and
# the translation data, plus a Read Me.
#
#   mac/build_dmg.sh [version]
set -euo pipefail
cd "$(dirname "$0")/.."

NAME="Vivo English Patcher"
VERSION="${1:-1.0.0}"
DMG="dist/Vivo-English-Patcher-$VERSION-mac.dmg"
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
APP="$STAGE/$NAME.app"

osacompile -o "$APP" "mac/installer/$NAME.applescript"

DATA="$APP/Contents/Resources/patcher"
mkdir -p "$DATA/mac"
cp mac/patch_vivo_mac.py "$DATA/mac/"
cp patches.json patches_vc.json literals.json map_en.json map_en2.json map_files.json \
   skip.json locales-en_US.js.new tinymce_langs_en_US_in.js LICENSE "$DATA/"

PLIST="$APP/Contents/Info.plist"
plutil -replace CFBundleIdentifier -string io.github.vivo-pcsuite-english.patcher "$PLIST"
plutil -replace CFBundleShortVersionString -string "$VERSION" "$PLIST"
plutil -replace CFBundleVersion -string "$VERSION" "$PLIST"
# not notarized: an ad hoc signature lets it run on Apple silicon
codesign --force --deep --sign - "$APP"

cp "mac/installer/Read Me.txt" "$STAGE/"
mkdir -p dist
hdiutil create -quiet -volname "$NAME" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
echo "$DMG"

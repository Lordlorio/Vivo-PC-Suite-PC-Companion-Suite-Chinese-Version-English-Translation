#!/bin/bash
# Double-click to put vivo PC Suite back to the original Chinese files.
cd "$(dirname "$0")" || exit 1
PY=$(command -v python3 || ls /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3 2>/dev/null | head -1)
if [ -z "$PY" ]; then
  echo "Python 3 is needed. Install it with:  xcode-select --install"
else
  "$PY" patch_vivo_mac.py --restore "$@"
fi
echo
read -n 1 -s -r -p "Press any key to close this window..."
echo

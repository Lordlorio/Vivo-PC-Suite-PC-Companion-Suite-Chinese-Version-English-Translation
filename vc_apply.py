# -*- coding: utf-8 -*-
"""Applique patches_vc.json sur vc_orig/ -> vc_patched/ (echoue bruyamment)."""
import json
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ORIG = os.path.join(HERE, 'vc_orig')
OUT = os.path.join(HERE, 'vc_patched')
PJSON = os.path.join(HERE, 'patches_vc.json')


def main():
    patches = json.load(open(PJSON, encoding='utf-8'))
    by_file = {}
    for p in patches:
        by_file.setdefault(p['file'], []).append(p)
    for rel, plist in sorted(by_file.items()):
        src = os.path.join(ORIG, *rel.split('/'))
        dst = os.path.join(OUT, *rel.split('/'))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        text = open(src, encoding='utf-8').read()
        for p in plist:
            cnt = text.count(p['old'])
            if cnt != p.get('expect', cnt):
                print('ECHEC %s count=%d expect=%s' % (rel, cnt, p.get('expect')))
                return 1
            if cnt == 0:
                print('ECHEC %s old introuvable' % rel)
                return 1
            text = text.replace(p['old'], p['new'])
        open(dst, 'w', encoding='utf-8', newline='').write(text)
        print('OK %s (%d patch)' % (rel, len(plist)))
    print('vc_patched: %d fichiers' % len(by_file))
    return 0


if __name__ == '__main__':
    sys.exit(main())

# -*- coding: utf-8 -*-
"""Extrait vivoControl app.asar vers vc_orig/ (l'asar n'est que lu)."""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build_asar import read_header, walk

SRC = (os.environ.get('VC_ASAR_SRC')
       or r'E:\Program Files\vivo\pcsuite\vivoControl\resources\app.asar')
OUT = os.path.join(HERE, 'vc_orig')


def main():
    with open(SRC, 'rb') as f:
        hj, base, _hs = read_header(f)
        hdr = json.loads(hj.decode('utf-8'))
        entries = [('/'.join(p), m) for p, m in walk(hdr['files'], [])]
    print('fichiers: %d' % len(entries))
    with open(SRC, 'rb') as f:
        for name, meta in entries:
            dest = os.path.join(OUT, *name.split('/'))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            f.seek(base + int(meta['offset']))
            left = int(meta['size'])
            with open(dest, 'wb') as out:
                while left:
                    chunk = f.read(min(1 << 20, left))
                    if not chunk:
                        print('ECHEC lecture %s' % name)
                        return 1
                    out.write(chunk)
                    left -= len(chunk)
    print('extrait vers: %s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())

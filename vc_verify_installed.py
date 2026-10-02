# -*- coding: utf-8 -*-
"""Verifie les marqueurs batch 35 dans les 2 asar installes."""
import json
import struct
import sys

sys.stdout.reconfigure(encoding='utf-8')
MAIN = r'E:\Program Files\vivo\pcsuite\resources\app.asar'
VC = (r'E:\Program Files\vivo\pcsuite\vivoControl\resources\app.asar')


def read_member(path, rel):
    with open(path, 'rb') as f:
        h = f.read(16)
        hs = struct.unpack('<I', h[12:16])[0]
        f.seek(16)
        j = json.loads(f.read(hs).decode('utf-8'))
        base = 12 + ((4 + hs + 3) // 4 * 4)

        def walk(node, p):
            for k, v in node.items():
                if isinstance(v, dict) and 'files' in v:
                    for it in walk(v['files'], p + [k]):
                        yield it
                elif isinstance(v, dict) and 'offset' in v:
                    yield p + [k], v
        for parts, meta in walk(j['files'], []):
            if '/'.join(parts) == rel:
                f.seek(base + int(meta['offset']))
                return f.read(int(meta['size'])).decode('utf-8')
    return None


CHECKS = [
    (MAIN, 'dist/electron/renderer.js', 'window.vclawName=v?"Jovi":"V Claw"'),
    (MAIN, 'dist/electron/main.js', '?"Jovi":"V Claw"'),
    (VC, 'dist/renderer.js', 'return"vus"'),
    (VC, 'dist/3.js', 'this.isEx=!0}'),
    (VC, 'dist/3.js', 'Welcome to vivo Remote PC'),
    (VC, 'dist/3.js', 'Device code'),
    (VC, 'dist/1.js', 'this.isEx=!0,'),
]
OLD = [
    (MAIN, 'dist/electron/renderer.js', '"Jovi":"小V Claw"'),
    (VC, 'dist/3.js', '欢迎使用vivo远控PC'),
    (VC, 'dist/renderer.js', 'return"vzh_rCN"'),
]


def main():
    bad = 0
    for path, rel, marker in CHECKS:
        t = read_member(path, rel)
        ok = t is not None and marker in t
        print('%s %s [%s]' % ('OK  ' if ok else 'MANQUE', rel, marker[:45]))
        bad += not ok
    for path, rel, marker in OLD:
        t = read_member(path, rel)
        gone = t is not None and marker not in t
        print('%s %s (ancien absent)' % ('OK  ' if gone else 'RESTE', rel))
        bad += not gone
    print('RESULTAT:', 'OK' if bad == 0 else 'ECHEC(%d)' % bad)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())

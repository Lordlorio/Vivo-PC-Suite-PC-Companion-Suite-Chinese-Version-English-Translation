# -*- coding: utf-8 -*-
"""Cherche des retours a la ligne reels introduits dans les bundles minifies."""
import json, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inject_locales import walk
sys.stdout.reconfigure(encoding='utf-8')
ASAR = sys.argv[1] if len(sys.argv) > 1 else (os.environ.get('PC_ASAR_DST') or r'E:\Program Files\vivo\pcsuite\resources\app.asar')
SRC = os.environ.get('PC_ASAR_SRC') or r'E:\Program Files\vivo\_backup_vivo_original_20260930\app.asar'


def load(path):
    f = open(path, 'rb')
    h = f.read(16)
    hs = struct.unpack('<I', h[12:16])[0]
    f.seek(16)
    hdr = json.loads(f.read(hs).decode('utf-8'))
    base = 12 + ((4 + hs + 3) // 4 * 4)
    ent = {('/'.join(p)): m for p, m in walk(hdr['files'], [])}
    return f, base, ent


fa, ba, ea = load(ASAR)
fo, bo, eo = load(SRC)
bad = []
for name in sorted(ea):
    if not name.startswith('dist/electron/') or name.rsplit('.', 1)[-1] != 'js':
        continue
    if '/static/' in name or name.rsplit('/', 1)[-1].startswith('locales-'):
        continue
    fa.seek(ba + int(ea[name]['offset']))
    a = fa.read(int(ea[name]['size']))
    n_a = a.count(b'\n') + a.count(b'\r')
    if n_a == 0:
        continue
    n_o = 0
    if name in eo:
        fo.seek(bo + int(eo[name]['offset']))
        o = fo.read(int(eo[name]['size']))
        n_o = o.count(b'\n') + o.count(b'\r')
    if n_a > n_o:
        bad.append((name, n_o, n_a))
        print('NOUVEAUX RETOURS A LA LIGNE: %s  %d -> %d' % (name, n_o, n_a))
        t = a.decode('utf-8', 'replace')
        for i, ch in enumerate(t):
            if ch in '\n\r':
                print('    @%d %r' % (i, t[max(0, i - 70):i + 70]))
fa.close()
fo.close()
print('fichiers concernes:', len(bad))

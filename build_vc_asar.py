# -*- coding: utf-8 -*-
"""Reconstruit vivoControl app.asar depuis l'asar installe + vc_patched/.

Clone minimal de build_asar.py (pas de EDITS/ADD) : REPLACE = vc_patched/.
Ecrit <DST>.new, ne remplace jamais DST.
"""
import hashlib
import json
import os
import struct
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))

SRC = (os.environ.get('VC_ASAR_SRC')
       or r'E:\Program Files\vivo\pcsuite\vivoControl\resources\app.asar')
DST = (os.environ.get('VC_ASAR_DST')
       or r'E:\Program Files\vivo\pcsuite\vivoControl\resources\app.asar')
PATCHED = os.path.join(HERE, 'vc_patched')
BLOCK = 4194304


def align4(x):
    return (x + 3) // 4 * 4


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def make_integrity(data):
    blocks = [sha256(data[i:i + BLOCK]) for i in range(0, len(data), BLOCK)] or []
    return {'algorithm': 'SHA256', 'hash': sha256(data), 'blockSize': BLOCK,
            'blocks': blocks}


def walk(node, path):
    for k, v in node.items():
        if isinstance(v, dict) and 'files' in v:
            for item in walk(v['files'], path + [k]):
                yield item
        elif isinstance(v, dict) and 'offset' in v:
            yield path + [k], v


def read_header(fh):
    head = fh.read(64)
    assert struct.unpack('<I', head[0:4])[0] == 4, 'en-tete asar inattendu'
    hs = struct.unpack('<I', head[12:16])[0]
    fh.seek(16)
    j = fh.read(hs)
    base = 12 + align4(4 + hs)
    return j, base, hs


def main():
    replace = {}
    for root, _dirs, files in os.walk(PATCHED):
        for fn in files:
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, PATCHED).replace(os.sep, '/')
            replace[rel] = full
    print('vc_patched/: %d fichiers' % len(replace))
    if not replace:
        print('ECHEC rien a remplacer')
        return 1

    with open(SRC, 'rb') as f:
        header_json, old_base, hs = read_header(f)
    hdr = json.loads(header_json.decode('utf-8'))
    entries = [(('/'.join(p)), m) for p, m in walk(hdr['files'], [])]
    print('fichiers header:', len(entries))

    missing = [r for r in replace if r not in dict(entries)]
    if missing:
        print('ECHEC cibles absentes du header:', missing)
        return 1

    modified = {}
    with open(SRC, 'rb') as f:
        for name in replace:
            meta = dict(entries)[name]
            f.seek(old_base + int(meta['offset']))
            orig = f.read(int(meta['size']))
            data = open(replace[name], 'rb').read()
            print('remplace: %s %d -> %d octets' % (name, len(orig), len(data)))
            modified[name] = data

    new_offset = 0
    old_offsets = {}
    old_sizes = {}
    for name, meta in entries:
        old_offsets[name] = int(meta['offset'])
        old_sizes[name] = int(meta['size'])
        if name in modified:
            meta['size'] = len(modified[name])
            meta['integrity'] = make_integrity(modified[name])
        meta['offset'] = str(new_offset)
        new_offset += int(meta['size'])

    new_json = json.dumps(hdr, separators=(',', ':'),
                          ensure_ascii=False).encode('utf-8')
    new_header_size = len(new_json)
    new_pickle2 = align4(4 + new_header_size)
    new_data_start = 12 + new_pickle2

    tmp = DST + '.new'
    with open(tmp, 'wb') as out, open(SRC, 'rb') as src:
        out.write(struct.pack('<IIII', 4, 4 + new_pickle2, new_pickle2,
                              new_header_size))
        out.write(new_json)
        out.write(b'\x00' * (new_pickle2 - (4 + new_header_size)))
        for name, meta in entries:
            if name in modified:
                out.write(modified[name])
            else:
                src.seek(old_base + old_offsets[name])
                left = int(meta['size'])
                while left:
                    chunk = src.read(min(1 << 20, left))
                    if not chunk:
                        print('ECHEC lecture', name)
                        return 1
                    out.write(chunk)
                    left -= len(chunk)
    print('ecrit:', tmp, os.path.getsize(tmp))

    # --- verification ---
    with open(tmp, 'rb') as f:
        h2, base2, hs2 = read_header(f)
        assert hs2 == new_header_size, 'header size'
        chk = json.loads(h2.decode('utf-8'))
    centries = [(('/'.join(p)), m) for p, m in walk(chk['files'], [])]
    if len(centries) != len(entries):
        print('ECHEC nb fichiers', len(centries), len(entries))
        return 1
    prev = 0
    for name, meta in centries:
        o, s = int(meta['offset']), int(meta['size'])
        if o != prev:
            print('ECHEC trou a', name, o, prev)
            return 1
        prev = o + s
    if prev != new_offset:
        print('ECHEC fin donnees', prev, new_offset)
        return 1
    cdict = dict(centries)
    with open(tmp, 'rb') as f:
        for name in modified:
            m = cdict[name]
            f.seek(base2 + int(m['offset']))
            data = f.read(int(m['size']))
            if data != modified[name]:
                print('ECHEC contenu', name)
                return 1
            if sha256(data) != m['integrity']['hash']:
                print('ECHEC hash', name)
                return 1
            if name.startswith('dist/') and name.endswith('.js'):
                with open(SRC, 'rb') as f1:
                    f1.seek(old_base + old_offsets[name])
                    orig = f1.read(old_sizes[name])
                if not (orig.count(b'\n') + orig.count(b'\r')) and \
                        (data.count(b'\n') + data.count(b'\r')):
                    print('ECHEC retours a la ligne introduits dans', name)
                    return 1
            print('OK %s (%d octets)' % (name, len(data)))
        samples = ['package.json', 'dist/main.js', 'dist/index.html',
                   'dist/renderer.js']
        for name in samples:
            if name in modified:
                continue
            m2 = cdict[name]
            with open(SRC, 'rb') as f1:
                f1.seek(old_base + old_offsets[name])
                a = f1.read(old_sizes[name])
            f.seek(base2 + int(m2['offset']))
            b = f.read(int(m2['size']))
            if a != b:
                print('ECHEC echantillon modifie', name)
                return 1
            print('identique:', name)
    print('VERIFICATION OK')
    print('sha256 final:', sha256(open(tmp, 'rb').read()).upper())
    return 0


if __name__ == '__main__':
    sys.exit(main())

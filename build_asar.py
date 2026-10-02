# -*- coding: utf-8 -*-
"""Reconstruit app.asar depuis la sauvegarde originale + tous les patches (Phase 1 + Phase 2 locales)."""
import json, struct, hashlib, sys, os, shutil

SRC = os.environ.get('PC_ASAR_SRC') or r'E:\Program Files\vivo\_backup_vivo_original_20260930\app.asar'
DST = os.environ.get('PC_ASAR_DST') or r'E:\Program Files\vivo\pcsuite\resources\app.asar'
HERE = os.path.dirname(os.path.abspath(__file__))
DQ = chr(34)
BLOCK = 4194304
NEW_LOCALES = os.path.join(HERE, 'locales-en_US.js.new')

# fichiers ABSENTS de la sauvegarde originale mais ajoutes au header :
# TinyMCE demande en_US_in (getEditorLanguage ajoute "_in" hors export) et
# seul zh_CN_in.js existait -> cles vivo affichees telles quelles.
ADD = {
    'dist/electron/static/tinymce/202609111200/langs/en_US_in.js':
        os.path.join(HERE, 'tinymce_langs_en_US_in.js'),
}

EDITS = {
    'dist/electron/renderer.js': [
        ('if(!n)return' + DQ + 'zh_CN', 'if(!n)return' + DQ + 'en_US'),
        ('n?o():' + DQ + 'zh_CN', 'n?o():' + DQ + 'en_US'),
        ('n?' + DQ + 'en_US' + DQ + ':' + DQ + 'zh_CN', 'n?' + DQ + 'en_US' + DQ + ':' + DQ + 'en_US'),
    ],
    'dist/electron/child-window.js': [
        ('if(!l)return' + DQ + 'zh_CN', 'if(!l)return' + DQ + 'en_US'),
        ('l?c():' + DQ + 'zh_CN', 'l?c():' + DQ + 'en_US'),
        ('l?' + DQ + 'en_US' + DQ + ':' + DQ + 'zh_CN', 'l?' + DQ + 'en_US' + DQ + ':' + DQ + 'en_US'),
    ],
    'dist/electron/module-share-preview.js': [
        ('if(!l)return' + DQ + 'zh_CN', 'if(!l)return' + DQ + 'en_US'),
        ('l?c():' + DQ + 'zh_CN', 'l?c():' + DQ + 'en_US'),
        ('l?' + DQ + 'en_US' + DQ + ':' + DQ + 'zh_CN', 'l?' + DQ + 'en_US' + DQ + ':' + DQ + 'en_US'),
    ],
}

REPLACE = {
    'dist/electron/locales-en_US.js': NEW_LOCALES,
}

PATCHED = os.path.join(HERE, 'patched')
if os.path.isdir(PATCHED):
    for _root, _dirs, _files in os.walk(PATCHED):
        for _fn in _files:
            if _fn == '_list.json':
                continue
            _full = os.path.join(_root, _fn)
            _rel = os.path.relpath(_full, PATCHED).replace(os.sep, '/')
            REPLACE[_rel] = _full
    print('patched/:', len(REPLACE) - 1, 'fichiers ajoutes')


def align4(x):
    return (x + 3) // 4 * 4


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def make_integrity(data):
    blocks = [sha256(data[i:i + BLOCK]) for i in range(0, len(data), BLOCK)] or []
    return {'algorithm': 'SHA256', 'hash': sha256(data), 'blockSize': BLOCK, 'blocks': blocks}


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
    if not os.path.exists(NEW_LOCALES):
        print('ECHEC locales-en_US.js.new absent')
        return 1

    with open(SRC, 'rb') as f:
        header_json, old_base, hs = read_header(f)
    hdr = json.loads(header_json.decode('utf-8'))
    added = {}
    for rel, srcp in ADD.items():
        if not os.path.exists(srcp):
            print('ECHEC fichier ajoute absent:', srcp)
            return 1
        content = open(srcp, 'rb').read()
        parts = rel.split('/')
        node = hdr['files']
        for part in parts[:-1]:
            if part not in node or 'files' not in node[part]:
                print('ECHEC dossier absent dans le header:', rel)
                return 1
            node = node[part]['files']
        if parts[-1] in node:
            print('ECHEC deja present dans le header:', rel)
            return 1
        node[parts[-1]] = {'size': len(content), 'offset': '0',
                           'integrity': make_integrity(content)}
        added[rel] = content
        print('ajoute: %s (%d octets)' % (rel, len(content)))
    entries = [(('/'.join(p)), m) for p, m in walk(hdr['files'], [])]
    print('fichiers header:', len(entries))

    modified = {}
    with open(SRC, 'rb') as f:
        for name, meta in entries:
            if name in EDITS:
                if name in REPLACE:
                    text = open(REPLACE[name], encoding='utf-8', newline='').read()
                    base_size = len(text.encode('utf-8'))
                else:
                    f.seek(old_base + int(meta['offset']))
                    text = f.read(int(meta['size'])).decode('utf-8')
                    base_size = int(meta['size'])
                for old, new in EDITS[name]:
                    cnt = text.count(old)
                    if cnt == 0 and text.count(new) > 0:
                        continue
                    if cnt != 1:
                        print('ECHEC motif %s %r count=%d' % (name, old, cnt))
                        return 1
                    if len(old) != len(new):
                        print('ECHEC longueur motif')
                        return 1
                    text = text.replace(old, new, 1)
                data = text.encode('utf-8')
                if len(data) != base_size:
                    print('ECHEC taille apres edition', name, base_size, len(data))
                    return 1
                modified[name] = data
                print('edite+remplace: %s (%d octets, %d remplacements)' % (name, len(data), len(EDITS[name])))
            elif name in REPLACE:
                data = open(REPLACE[name], 'rb').read()
                print('remplace: %s %d -> %d octets' % (name, int(meta['size']), len(data)))
                modified[name] = data

    for rel, content in added.items():
        modified[rel] = content

    expected = set(EDITS) | set(REPLACE) | set(added)
    if set(modified) != expected:
        print('ECHEC cibles manquantes', expected - set(modified))
        return 1

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
    print('nouvelles donnees:', new_offset)

    new_json = json.dumps(hdr, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    new_header_size = len(new_json)
    new_pickle2 = align4(4 + new_header_size)
    new_data_start = 12 + new_pickle2
    print('header %d -> %d, data_start %d -> %d' % (hs, new_header_size, old_base, new_data_start))

    tmp = DST + '.new'
    with open(tmp, 'wb') as out, open(SRC, 'rb') as src:
        out.write(struct.pack('<IIII', 4, 4 + new_pickle2, new_pickle2, new_header_size))
        out.write(new_json)
        pad = new_pickle2 - (4 + new_header_size)
        assert pad >= 0, pad
        out.write(b'\x00' * pad)
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
            # garde-fou : un bundle minifie d'origine sans retour a la ligne ne
            # doit pas en acquerir (une chaine JS sur 2 lignes = SyntaxError).
            if name.startswith('dist/electron/') and name.endswith('.js') \
                    and '/static/' not in name \
                    and not name.rsplit('/', 1)[-1].startswith('locales-'):
                with open(SRC, 'rb') as f1:
                    f1.seek(old_base + old_offsets[name])
                    orig = f1.read(old_sizes[name])
                if not (orig.count(b'\n') + orig.count(b'\r')) and (data.count(b'\n') + data.count(b'\r')):
                    print('ECHEC retours a la ligne introduits dans', name)
                    return 1
            print('OK %s (%d octets)' % (name, len(data)))
        samples = ['node_modules/@author.io/arg/package.json', 'dist/electron/main.js',
                   'dist/electron/locales-zh_CN.js', 'dist/electron/index.html',
                   'dist/electron/build-config.json', 'dist/electron/app-modules.js',
                   'dist/electron/locales-en_US.js', 'dist/electron/renderer.js']
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

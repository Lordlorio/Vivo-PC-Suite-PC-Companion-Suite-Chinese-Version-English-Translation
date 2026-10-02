# -*- coding: utf-8 -*-
"""Verification complete d'un asar : header, contiguite, integrite totale, patches, cles traduites."""
import json, struct, hashlib, sys, os, re, collections

ASAR = sys.argv[1] if len(sys.argv) > 1 else r'E:\Program Files\vivo\pcsuite\resources\app.asar.new'
DQ = chr(34)
HERE = os.path.dirname(os.path.abspath(__file__))

LITS = [
    'if(!n)return' + DQ + 'zh_CN',
    'n?o():' + DQ + 'zh_CN',
    'n?' + DQ + 'en_US' + DQ + ':' + DQ + 'zh_CN',
    'if(!l)return' + DQ + 'zh_CN',
    'l?c():' + DQ + 'zh_CN',
    'l?' + DQ + 'en_US' + DQ + ':' + DQ + 'zh_CN',
]


def align4(x):
    return (x + 3) // 4 * 4


def walk(node, path):
    for k, v in node.items():
        if isinstance(v, dict) and 'files' in v:
            for item in walk(v['files'], path + [k]):
                yield item
        elif isinstance(v, dict) and 'offset' in v:
            yield path + [k], v


def main():
    with open(ASAR, 'rb') as f:
        head = f.read(16)
        assert struct.unpack('<I', head[0:4])[0] == 4
        hs = struct.unpack('<I', head[12:16])[0]
        f.seek(16)
        j = f.read(hs)
    base = 12 + align4(4 + hs)
    hdr = json.loads(j.decode('utf-8'))
    entries = [(('/'.join(p)), m) for p, m in walk(hdr['files'], [])]
    print('fichiers:', len(entries))

    prev = 0
    bad_contig = []
    for name, m in entries:
        o, s = int(m['offset']), int(m['size'])
        if o != prev:
            bad_contig.append((name, o, prev))
        prev = o + s
    assert not bad_contig, bad_contig[:5]
    print('contiguite OK, donnees:', prev, 'taille fichier:', os.path.getsize(ASAR),
          'attendu:', base + prev, 'ecart:', os.path.getsize(ASAR) - (base + prev))

    # integrite de TOUS les fichiers
    bad = []
    nhash = 0
    with open(ASAR, 'rb') as f:
        for name, m in entries:
            if 'integrity' not in m:
                continue
            f.seek(base + int(m['offset']))
            data = f.read(int(m['size']))
            h = hashlib.sha256(data).hexdigest()
            it = m['integrity']
            if h != it['hash']:
                bad.append(('hash', name))
            blocks = [hashlib.sha256(data[i:i + it['blockSize']]).hexdigest()
                      for i in range(0, len(data), it['blockSize'])] or []
            if blocks != it['blocks']:
                bad.append(('blocks', name))
            nhash += 1
    print('integrite verifiee:', nhash, 'fichiers, echecs:', len(bad))
    for b in bad[:20]:
        print('   ', b)
    if bad:
        return 1

    def get(name):
        for n, m in entries:
            if n == name:
                f = open(ASAR, 'rb')
                f.seek(base + int(m['offset']))
                d = f.read(int(m['size']))
                f.close()
                return d
        raise KeyError(name)

    # patches locales
    for name in ('dist/electron/renderer.js', 'dist/electron/child-window.js',
                 'dist/electron/module-share-preview.js'):
        t = get(name).decode('utf-8')
        for lit in LITS:
            if lit in t:
                print('RESIDUEL', name, lit)
                return 1
        if t.count('zh_CN') > 0:
            print('note: %s contient encore %d "zh_CN"' % (name, t.count('zh_CN')))
        print('OK patches locale:', name)

    # cles traduites
    sys.path.insert(0, HERE)
    from inject_locales import unescape_js, MAP_PAT, MAPITEM_PAT

    def payloads_of(name):
        t = get(name).decode('utf-8')
        best = None
        for m in MAP_PAT.finditer(t):
            items = MAPITEM_PAT.findall(m.group(0))
            if best is None or len(items) > len(best):
                best = items
        out = {}
        for fname, mid in best:
            m = re.search(re.escape(mid) + r":function\(e\)\{e\.exports=JSON\.parse\('((?:[^'\\]|\\.)*)'\)\}", t)
            if not m:
                continue
            obj = json.loads(unescape_js(m.group(1)))
            if isinstance(obj, dict) and obj:
                out[fname[2:-5]] = obj
        return out

    en_ns = payloads_of('dist/electron/locales-en_US.js')
    zh_ns = payloads_of('dist/electron/locales-zh_CN.js')
    merged = {}
    for ns, o in en_ns.items():
        print('  %s: %d cles' % (ns, len(o)))
        merged.update(o)
    print('cles totales en_US (fusion):', len(merged))

    missing = json.load(open(os.path.join(HERE, 'missing_keys.json'), encoding='utf-8'))
    absent = [k for k in missing if k.split('.', 1)[1] in merged and merged[k.split('.', 1)[1]] == missing[k]]
    truly = [k for k in missing if k.split('.', 1)[1] not in merged]
    print('cles toujours absentes:', len(truly))
    for a in truly[:20]:
        print('   ', a)
    if truly:
        return 1

    left = []
    for ns, zo in zh_ns.items():
        eo = en_ns.get(ns, {})
        for k, v in zo.items():
            if k not in eo:
                left.append(('%s.%s' % (ns, k), v))
    print('cles zh sans equivalent en_US:', len(left))
    for k, v in left[:40]:
        print('   ', k, '=', v)

    print('VERIFICATION COMPLETE OK')
    print('sha256:', hashlib.sha256(open(ASAR, 'rb').read()).hexdigest().upper())
    return 0


if __name__ == '__main__':
    sys.exit(main())

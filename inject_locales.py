# -*- coding: utf-8 -*-
"""Injecte les traductions manquantes dans locales-en_US.js et produit le fichier remplace."""
import json, struct, re, os, sys
import translations_en

ASAR = os.environ.get('PC_ASAR_SRC') or r'E:\Program Files\vivo\pcsuite\resources\app.asar'
HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = 'dist/electron/locales-en_US.js'
OUT = os.path.join(HERE, 'locales-en_US.js.new')

MOD_PAT = re.compile(r"(\d+):function\(e\)\{e\.exports=JSON\.parse\('((?:[^'\\]|\\.)*)'\)\}")
MAP_PAT = re.compile(r'\{("\./[A-Za-z]+\.json":\d+,?)+\}')
MAPITEM_PAT = re.compile(r'"(\./[A-Za-z]+\.json)":(\d+)')


def walk(node, path):
    for k, v in node.items():
        if isinstance(v, dict) and 'files' in v:
            for item in walk(v['files'], path + [k]):
                yield item
        elif isinstance(v, dict) and 'offset' in v:
            yield path + [k], v


def read_member(name):
    d = open(ASAR, 'rb').read(8000000)
    hs = struct.unpack('<I', d[12:16])[0]
    hdr = json.loads(d[16:16 + hs].decode('utf-8'))
    base = 12 + ((4 + hs + 3) // 4 * 4)
    for n, m in walk(hdr['files'], []):
        if '/'.join(n) == name:
            f = open(ASAR, 'rb')
            f.seek(base + int(m['offset']))
            return f.read(int(m['size'])).decode('utf-8')
    raise KeyError(name)


def unescape_js(s):
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if c != '\\':
            out.append(c)
            i += 1
            continue
        i += 1
        if i >= len(s):
            break
        n = s[i]
        if n == 'n':
            out.append('\n')
        elif n == 't':
            out.append('\t')
        elif n == 'r':
            out.append('\r')
        elif n == 'u':
            out.append(chr(int(s[i + 1:i + 5], 16)))
            i += 4
        else:
            out.append(n)
        i += 1
    return ''.join(out)


def escape_js(s):
    out = []
    for c in s:
        if c == '\\':
            out.append('\\\\')
        elif c == "'":
            out.append("\\'")
        elif c == '\n':
            out.append('\\n')
        elif c == '\r':
            out.append('\\r')
        elif c == '\t':
            out.append('\\t')
        elif c in '\u2028\u2029':
            out.append('\\u%04x' % ord(c))
        else:
            out.append(c)
    return ''.join(out)


def main():
    missing = json.load(open(os.path.join(HERE, 'missing_keys.json'), encoding='utf-8'))
    trans = translations_en.build()
    non_covers = sorted(set(missing) - set(trans))
    extras = sorted(set(trans) - set(missing))
    print('manquantes:', len(missing), 'traductions:', len(trans))
    print('SANS traduction:', len(non_covers))
    for k in non_covers:
        print('   ', k, '=', missing[k])
    print('traductions superflues:', len(extras))
    if non_covers:
        print('ABANDON: traductions incompletes')
        return 1

    text = read_member(TARGET)
    best = None
    for m in MAP_PAT.finditer(text):
        items = MAPITEM_PAT.findall(m.group(0))
        if best is None or len(items) > len(best):
            best = items
    ns_to_id = {fname[2:-5]: mid for fname, mid in best}
    print('contexte:', ns_to_id)

    by_ns = {}
    for full, val in trans.items():
        ns, key = full.split('.', 1)
        by_ns.setdefault(ns, {})[key] = val

    inserts = 0
    for ns, kv in by_ns.items():
        mid = ns_to_id[ns]
        m = re.search(re.escape(mid) + r":function\(e\)\{e\.exports=JSON\.parse\('((?:[^'\\]|\\.)*)'\)\}", text)
        assert m, 'module introuvable pour ' + ns
        payload = json.loads(unescape_js(m.group(1)))
        before = len(payload)
        for k, v in kv.items():
            if k in payload:
                print('   deja present, ignore:', ns + '.' + k)
                continue
            payload[k] = v
            inserts += 1
        new_json = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
        new_src = "JSON.parse('" + escape_js(new_json) + "')"
        seg = m.group(0)
        old_parse = "JSON.parse('" + m.group(1) + "')"
        new_seg = seg.replace(old_parse, new_src)
        assert new_seg != seg, 'remplacement invalide ' + ns
        text = text[:m.start()] + new_seg + text[m.end():]
        print('  %s: %d -> %d cles' % (ns, before, len(payload)))

    print('insertions:', inserts)
    open(OUT, 'w', encoding='utf-8', newline='').write(text)

    # verification : reparse
    text2 = open(OUT, encoding='utf-8').read()
    tot = 0
    for ns, mid in ns_to_id.items():
        m = re.search(re.escape(mid) + r":function\(e\)\{e\.exports=JSON\.parse\('((?:[^'\\]|\\.)*)'\)\}", text2)
        if not m:
            m2 = re.search(re.escape(mid) + r':function\(e\)\{e\.exports=JSON\.parse\("((?:[^"\\]|\\.)*)"\)\}', text2)
            assert m2, ns
            json.loads(unescape_js(m2.group(1)))
            print('  %s: payload vide (double quote)' % ns)
            continue
        obj = json.loads(unescape_js(m.group(1)))
        tot += len(obj)
    print('verification OK, total cles en_US:', tot)
    print('ecrit:', OUT, os.path.getsize(OUT))
    return 0


if __name__ == '__main__':
    sys.exit(main())

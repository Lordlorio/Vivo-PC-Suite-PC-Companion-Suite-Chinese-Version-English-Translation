# -*- coding: utf-8 -*-
"""Applique les traductions de litteraux aux fichiers de l'asar -> repertoir patched/."""
import json, os, sys, struct, collections, re

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from inject_locales import walk

# base de depart : la sauvegarde originale (idempotent, reproductible).
# ne JAMAIS lire l'asar installe : un fichier deja traduit n'aurait plus de spans
# et serait alors perdu par build_asar (SRC = sauvegarde originale).
ASAR = os.environ.get('PC_ASAR_SRC') or r'E:\Program Files\vivo\_backup_vivo_original_20260930\app.asar'
OUT = os.path.join(HERE, 'patched')
DRY = '--apply' not in sys.argv
SKIP_FILES = {
    'dist/electron/174.js', 'dist/electron/188.js',
}


def is_skipped(n):
    if n in SKIP_FILES:
        return True
    bn = n.rsplit('/', 1)[-1]
    return n.startswith('dist/electron/locales-') and bn.endswith('.js')


def main():
    lits = json.load(open(os.path.join(HERE, 'literals.json'), encoding='utf-8'))
    mp = {}
    for fn in sorted(os.listdir(HERE)):
        if fn.startswith('map_en') and fn.endswith('.json'):
            mp.update(json.load(open(os.path.join(HERE, fn), encoding='utf-8')))
            print('dico:', fn)
    mf = json.load(open(os.path.join(HERE, 'map_files.json'), encoding='utf-8')) \
        if os.path.exists(os.path.join(HERE, 'map_files.json')) else {}
    patches = json.load(open(os.path.join(HERE, 'patches.json'), encoding='utf-8')) \
        if os.path.exists(os.path.join(HERE, 'patches.json')) else []

    f = open(ASAR, 'rb')
    h = f.read(16)
    hs = struct.unpack('<I', h[12:16])[0]
    f.seek(16)
    j = f.read(hs)
    base = 12 + ((4 + hs + 3) // 4 * 4)
    hdr = json.loads(j.decode('utf-8'))
    entries = {('/'.join(p)): m for p, m in walk(hdr['files'], [])}
    cache = {}

    def txt(name):
        if name not in cache:
            m = entries[name]
            f.seek(base + int(m['offset']))
            cache[name] = f.read(int(m['size'])).decode('utf-8')
        return cache[name]

    spans = collections.defaultdict(list)   # file -> list of (start, end, new)
    seen = set()
    missing = []
    used = 0
    per_lit = collections.Counter()

    def _norm(s):
        # normalise uniquement pour RECHERCHER la vraie cle dans literals.json :
        # les cles de literals.json contiennent le source JS brut (\\n, \\", ...).
        s = s.replace('\r\n', '\\n').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
        s = re.sub(r'\\+', r'\\', s)
        return s.replace('\\"', '"')

    norm_index = {}
    for k in lits:
        nk = _norm(k)
        if nk not in norm_index or len(k) < len(norm_index[nk]):
            norm_index[nk] = k

    def esc(new, orig, q):
        """Met en forme la traduction comme le fragment JS remplace."""
        new = new.replace('\\', '\\\\')
        if '\n' not in orig and '\\n' in orig:
            new = new.replace('\n', '\\n')
        if '\r' not in orig and '\\r' in orig:
            new = new.replace('\r', '\\r')
        if '\t' not in orig and '\\t' in orig:
            new = new.replace('\t', '\\t')
        if q == '"':
            new = new.replace('"', '\\"')
        elif q == "'":
            new = new.replace("'", "\\'")
        elif q == '`' and '${' in new:
            new = new.replace('${', '\\${')
        return new

    UI_FILES = [n for n in sorted(entries)
                if n.startswith('dist/electron/') and not is_skipped(n)
                and not n.startswith('dist/electron/static/')
                and n.rsplit('.', 1)[-1] in ('js', 'html')]

    # spans explicitement a ne pas toucher (comparaison vs donnees serveur)
    skip_path = os.path.join(HERE, 'skip.json')
    skipset = {}
    if os.path.exists(skip_path):
        skipset = {k: set(v) for k, v in
                   json.load(open(skip_path, encoding='utf-8')).items()}
        print('skip.json:', {k: len(v) for k, v in skipset.items()})

    def iskip(fn, s):
        return s in skipset.get(fn, ())

    for lit, en in mp.items():
        allow = set(mf.get(lit, [])) or None
        key = lit
        if key not in lits:
            r = norm_index.get(_norm(key))
            if r is not None:
                key = r
        # forme a chercher dans le source : dans les bundles les retours a la
        # ligne des chaines sont des \\n litteraux (une cle avec un vrai \\n ne
        # serait jamais trouvee par les balayages ci-dessous).
        skey = key.replace('\r\n', '\\n').replace('\n', '\\n') \
                  .replace('\r', '\\r').replace('\t', '\\t')
        # 1) occurrences connues dans literals.json
        for o in lits.get(key, []):
            fn = o['f']
            bn = fn.rsplit('/', 1)[-1]
            if allow and bn not in allow:
                continue
            s = o['i'] + 1
            e = s + len(skey)
            if (fn, s) in seen:
                continue
            # les indexes de literals.json peuvent etre stale : on exige que le
            # fragment lu dans le fichier soit exactement la cle et soit bien
            # entoure de guillemets, sinon on laisse les balayages ci-dessous
            # retrouver l'occurrence par contenu.
            t = txt(fn)
            if s - 1 >= len(t) or t[s - 1] not in '"\'`' or t[s:e] != skey or t[e:e + 1] not in '"\'`':
                continue
            seen.add((fn, s))
            if iskip(fn, s):
                continue
            spans[fn].append((s, e, en, True, False))
            used += 1
            per_lit[lit] += 1
        # 2) balayage direct dans les fichiers autorises (litteral absent/incorrect
        #    dans literals.json a cause de guillemets non equilibres)
        targets = sorted('dist/electron/' + b for b in allow) if allow else UI_FILES

        def scan(names, closed):
            nonlocal used
            for fn in names:
                if fn not in entries:
                    print('ECHEC fichier inconnu', fn)
                    return False
                t = txt(fn)
                for q in ('"', "'", '`'):
                    # on n'ecarte q que s'il est present NON echappe dans la
                    # cle : les cles brutes de literals.json contiennent parfois
                    # \" (guillemet echappe dans la chaine source).
                    if re.search(r'(?<!\\)' + re.escape(q), skey):
                        continue
                    st = 0
                    while True:
                        if closed:
                            i = t.find(q + skey + q, st)
                        else:
                            # ouverture seule : la chaine est fermee plus loin
                            i = t.find(q + skey, st)
                        if i < 0:
                            break
                        st = i + 1
                        if (fn, i + 1) in seen:
                            continue
                        seen.add((fn, i + 1))
                        if iskip(fn, i + 1):
                            continue
                        spans[fn].append((i + 1, i + 1 + len(skey), en, closed, False))
                        used += 1
                        per_lit[lit] += 1
            return True

        # 3) chaines entierement blanchees autour de la cle
        #    ("\\n            browse\\n          ") : le balayage ci-dessus
        #    n'exige pas de trouver la cle seule entre guillemets.
        PAD = r'(?:[ \t\r\n]|\\[nrt])*'

        def scan_padded(names):
            nonlocal used
            for fn in names:
                if fn not in entries:
                    print('ECHEC fichier inconnu', fn)
                    return False
                t = txt(fn)
                for q in ('"', "'", '`'):
                    if re.search(r'(?<!\\)' + re.escape(q), skey):
                        continue
                    pat = re.compile(re.escape(q) + r'(' + PAD + ')'
                                     + re.escape(skey) + r'(' + PAD + ')'
                                     + re.escape(q))
                    for m in pat.finditer(t):
                        if m.start() == 0 or t[m.start() - 1] == '\\':
                            continue
                        s = m.start() + 1
                        e = m.end() - 1
                        if (fn, s) in seen:
                            continue
                        if m.group(1) == '' and m.group(2) == '':
                            continue
                        seen.add((fn, s))
                        if iskip(fn, s):
                            continue
                        newraw = m.group(1) + esc(en, skey, q) + m.group(2)
                        spans[fn].append((s, e, newraw, True, True))
                        used += 1
                        per_lit[lit] += 1
            return True

        if not scan_padded(targets):
            return 1
        if per_lit[lit] == 0 and len(skey) >= 4 and allow is None and not scan_padded(UI_FILES):
            return 1

        if not scan(targets, True):
            return 1
        if per_lit[lit] == 0 and len(skey) >= 4 and allow is None and not scan(UI_FILES, True):
            return 1
        if per_lit[lit] == 0 and len(skey) >= 4 and not scan(targets, False):
            return 1

    for lit in mp:
        if per_lit[lit] == 0 and lit not in missing:
            missing.append(lit)

    print('litteraux du dico:', len(mp), 'occurrences remplacees:', used)
    if missing:
        print('CLES SANS OCCURRENCE:')
        for m in missing:
            extra = ''
            k = m
            if k not in lits:
                r = norm_index.get(_norm(k))
                if r is not None:
                    k = r
            if k in lits:
                extra = '   (dans ' + str(sorted({o["f"].rsplit("/", 1)[-1] for o in lits[k]})) + ')'
            print('   ', json.dumps(m, ensure_ascii=False), extra)

    for fn in sorted(spans, key=lambda x: -len(spans[x])):
        print('   %4d  %s' % (len(spans[fn]), fn))
    rep = []
    for fn in sorted(spans):
        t = txt(fn)
        for s, e, new, cl, raw in spans[fn]:
            shown = new if raw else esc(new, t[s:e], t[s - 1])
            rep.append('%s@%d%s%s\n    OLD %s\n    NEW %s' % (
                fn, s, '' if cl else ' [OUVERT]', ' [BLANCHE]' if raw else '',
                json.dumps(t[s:e], ensure_ascii=False),
                json.dumps(shown, ensure_ascii=False)))
    with open(os.path.join(HERE, 'report_literals.txt'), 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(rep))

    changed = {}
    for fn, sp in spans.items():
        sp.sort()
        # retire les spans entierement contenus dans un autre span (litteral plus long)
        keep = []
        for s in sp:
            if any(o[0] <= s[0] and s[1] <= o[1] and o is not s for o in sp):
                continue
            keep.append(s)
        sp = keep
        spans[fn] = sp
        for a, b in zip(sp, sp[1:]):
            if a[1] > b[0]:
                print('ECHEC chevauchement', fn, a[:2], b[:2])
                return 1
        t = txt(fn)
        out = []
        prev = 0
        for s, e, new, cl, raw in sp:
            if t[s - 1] not in '"\'`':
                print('ECHEC quote', fn, s, repr(t[s - 1:s + 3]))
                return 1
            if cl and t[e] not in '"\'`':
                print('ECHEC quote fin', fn, s, repr(t[e - 3:e + 1]))
                return 1
            out.append(t[prev:s])
            out.append(new if raw else esc(new, t[s:e], t[s - 1]))
            prev = e
        out.append(t[prev:])
        changed[fn] = ''.join(out)

    # sondage des <title> html (hors node_modules)
    for n in sorted(entries):
        if not n.endswith('.html'):
            continue
        if n.startswith('node_modules/') or '/node_modules/' in n:
            continue
        t = changed.get(n) or txt(n)
        i = t.find('<title>')
        j = t.find('</title>')
        if i >= 0 and j > i:
            print('TITLE %s = %r' % (n, t[i + 7:j]))


    # patches directs (idempotents)
    for p in patches:
        fn = p['file']
        t = changed.get(fn) or txt(fn)
        c = t.count(p['old'])
        if c == 0 and p['new'] in t:
            continue
        if c != p.get('expect', 1):
            print('ECHEC patch %s count=%d attendu=%s  old=%r' % (fn, c, p.get('expect', 1), p['old'][:60]))
            return 1
        changed[fn] = t.replace(p['old'], p['new'])
        print('patch ok: %s x%d  %r' % (fn.rsplit('/', 1)[-1], c, p['old'][:60]))

    # securite : un bundle minifie d'origine ne contient aucun retour a la
    # ligne reel. Tout \n/\r apparu provient d'une traduction inseree dans une
    # chaine JS (SyntaxError "Invalid or unexpected token") -> on re-echappe :
    # la valeur JS de la chaine reste strictement identique.
    plain = {n for n in entries
             if n.startswith('dist/electron/') and n.endswith('.js')
             and '/static/' not in n
             and not n.rsplit('/', 1)[-1].startswith('locales-')
             and '\n' not in txt(n) and '\r' not in txt(n)}
    for fn in sorted(changed):
        if fn not in plain:
            continue
        t = changed[fn]
        if '\n' in t or '\r' in t:
            n2 = t.replace('\r\n', '\\n').replace('\n', '\\n').replace('\r', '\\r')
            print('NEWLINE repare: %s  %d -> %d' % (fn, len(t), len(n2)))
            changed[fn] = n2

    # verifications
    for fn, new in changed.items():
        old = txt(fn)
        print('%-42s %7d -> %7d octets  (%d cles)' % (fn.rsplit('/', 1)[-1], len(old.encode('utf-8')),
                                                      len(new.encode('utf-8')),
                                                      len(spans.get(fn, []))))

    if DRY:
        print('DRY RUN (pas d ecriture). Lancer avec --apply pour ecrire patched/')
        f.close()
        return 0

    import shutil
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    for fn, new in changed.items():
        path = os.path.join(OUT, *fn.split('/'))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8', newline='') as o:
            o.write(new)
    json.dump({'files': sorted(changed)}, open(os.path.join(OUT, '_list.json'), 'w'), indent=1)
    print('ecrits:', len(changed), 'fichiers dans', OUT)
    f.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())

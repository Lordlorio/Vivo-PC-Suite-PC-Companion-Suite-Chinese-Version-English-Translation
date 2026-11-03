#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""English patch for vivo PC Suite (vivo办公套件, China build) on macOS.

macOS counterpart of the Windows patcher in this repository. It reads the
same translation data from the repository root (patches.json, literals.json,
map_en*.json, ...), so keep this mac/ folder inside the repository.

The Windows release ships a pre-built app.asar for the Windows 7.0.5 build.
The Mac build is different (7.0.6, other chunk hashes, shifted module ids), so
this script rebuilds the archive from YOUR installed copy instead:

  1. hardcoded Chinese strings  -> English (map_en*.json)
  2. patches.json               -> exact rewrites, applied only when they match
                                   the Mac file exactly as they did on Windows
  3. en_US locale               -> missing English keys merged in
  4. default language           -> zh_CN becomes en_US
  5. CSS fixes for longer English labels, TinyMCE English language file
  6. Remote PC window (vcontrol.app) -> patches_vc.json
  7. optional (--mirror): Phone Mirroring (vivoScreen.app) default language

Originals are backed up to ~/Library/Application Support/pcsuite-english-patch
and put back with --restore.
"""
import argparse
import bisect
import collections
import datetime
import hashlib
import json
import mmap
import os
import plistlib
import pwd
import re
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.dirname(HERE)
DEFAULT_APP = '/Applications/pcsuite.app'
BUNDLE_ID = 'com.vivo.pcsuite'
PROJECT = 'https://github.com/Lordlorio/Vivo-PC-Suite-PC-Companion-Suite-Chinese-Version-English-Translation'
PATCHER_VERSION = '1.0.0'
MARKER = 'english-patch-mac.json'
BLOCK = 4 * 1024 * 1024
QUOTES = '"\'`'
CJK = re.compile('[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]')
CJK_RUN = re.compile('[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+')


def user_home():
    # under sudo, keep backups and settings in the real user's home
    name = os.environ.get('SUDO_USER')
    if os.geteuid() == 0 and name:
        return pwd.getpwnam(name).pw_dir
    return os.path.expanduser('~')


HOME = user_home()
SUPPORT = os.path.join(HOME, 'Library', 'Application Support', 'pcsuite')
BACKUP = os.path.join(HOME, 'Library', 'Application Support', 'pcsuite-english-patch')
STATE = os.path.join(BACKUP, 'state.json')

APP_MANAGEMENT_HELP = """macOS blocked writing into pcsuite.app.

Give the app you run this from (Terminal, or Vivo English Patcher) permission:
  System Settings > Privacy & Security > App Management > turn it on
then quit and reopen that app and run the patcher again."""


class Fail(Exception):
    pass


def say(msg=''):
    print(msg, flush=True)


def step(msg):
    say('==> ' + msg)


def note(msg):
    say('    ' + msg)


def confirm(question, assume_yes):
    if assume_yes:
        return True
    try:
        return input(question + ' [y/N] ').strip().lower() in ('y', 'yes')
    except EOFError:
        return False


def load_data(name):
    with open(os.path.join(DATA, name), encoding='utf-8') as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# asar archives
# ---------------------------------------------------------------------------

def align4(x):
    return (x + 3) // 4 * 4


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def integrity(data):
    return {'algorithm': 'SHA256', 'hash': sha256(data), 'blockSize': BLOCK,
            'blocks': [sha256(data[i:i + BLOCK]) for i in range(0, len(data), BLOCK)]}


def walk(node, path):
    for k, v in node.items():
        if isinstance(v, dict) and 'files' in v:
            yield from walk(v['files'], path + [k])
        elif isinstance(v, dict) and 'offset' in v and not v.get('unpacked'):
            yield '/'.join(path + [k]), v


class Asar:
    def __init__(self, path):
        self.path = path
        self.fh = open(path, 'rb')
        head = self.fh.read(16)
        if len(head) < 16 or struct.unpack('<I', head[:4])[0] != 4:
            self.fh.close()
            raise Fail('not an asar archive: ' + path)
        size = struct.unpack('<I', head[12:16])[0]
        self.header = json.loads(self.fh.read(size).decode('utf-8'))
        self.base = 12 + align4(4 + size)
        self.entries = dict(walk(self.header['files'], []))
        self._text = {}

    def read(self, name):
        meta = self.entries[name]
        self.fh.seek(self.base + int(meta['offset']))
        return self.fh.read(int(meta['size']))

    def text(self, name):
        if name not in self._text:
            self._text[name] = self.read(name).decode('utf-8')
        return self._text[name]

    def marker(self):
        if MARKER not in self.entries:
            return None
        return json.loads(self.read(MARKER).decode('utf-8'))

    def close(self):
        self.fh.close()


def write_asar(src, modified, added, dst):
    """Write src with `modified` files replaced and `added` files inserted."""
    hdr = json.loads(json.dumps(src.header))
    for rel, data in added.items():
        node = hdr['files']
        parts = rel.split('/')
        for part in parts[:-1]:
            node = node.setdefault(part, {'files': {}})['files']
        node[parts[-1]] = {'size': len(data), 'offset': '0', 'integrity': integrity(data)}

    plan = []
    offset = 0
    for name, meta in walk(hdr['files'], []):
        data = modified.get(name, added.get(name))
        if data is not None:
            meta['size'] = len(data)
            meta['integrity'] = integrity(data)
            plan.append((name, data, 0))
        else:
            plan.append((name, None, src.base + int(src.entries[name]['offset'])))
        meta['offset'] = str(offset)
        offset += int(meta['size'])

    blob = json.dumps(hdr, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    pickle = align4(4 + len(blob))
    with open(dst, 'wb') as out:
        out.write(struct.pack('<IIII', 4, 4 + pickle, pickle, len(blob)))
        out.write(blob)
        out.write(b'\0' * (pickle - 4 - len(blob)))
        for name, data, at in plan:
            if data is not None:
                out.write(data)
                continue
            src.fh.seek(at)
            left = int(src.entries[name]['size'])
            while left:
                chunk = src.fh.read(min(1 << 20, left))
                if not chunk:
                    raise Fail('short read in %s: %s' % (src.path, name))
                out.write(chunk)
                left -= len(chunk)

    # read it back: every offset contiguous, changed files byte-exact
    chk = Asar(dst)
    try:
        expect = set(src.entries) | set(added)
        if set(chk.entries) != expect:
            raise Fail('rebuilt archive has a different file list')
        pos = 0
        for name, meta in walk(chk.header['files'], []):
            if int(meta['offset']) != pos:
                raise Fail('rebuilt archive has a gap at ' + name)
            pos += int(meta['size'])
        for name, data in list(modified.items()) + list(added.items()):
            got = chk.read(name)
            if got != data or sha256(got) != chk.entries[name]['integrity']['hash']:
                raise Fail('rebuilt archive is wrong for ' + name)
        for name in list(src.entries)[::max(1, len(src.entries) // 40)]:
            if name not in modified and chk.read(name) != src.read(name):
                raise Fail('rebuilt archive changed ' + name)
    finally:
        chk.close()


# ---------------------------------------------------------------------------
# JS string helpers (from the Windows project's inject_locales.py / apply_literals.py)
# ---------------------------------------------------------------------------

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
        elif n == 'x':
            out.append(chr(int(s[i + 1:i + 3], 16)))
            i += 2
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


def source_form(key):
    # in minified bundles newlines inside strings are written as \n
    return key.replace('\r\n', '\\n').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')


def norm_key(s):
    # only used to FIND the matching key in literals.json (raw JS source keys)
    s = source_form(s)
    s = re.sub(r'\\+', r'\\', s)
    return s.replace('\\"', '"')


def esc(new, orig, q):
    """Format a translation like the JS string fragment it replaces."""
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


def bigrams(s):
    out = set()
    for run in CJK_RUN.findall(s):
        if len(run) == 1:
            out.add(run)
        out.update(run[i:i + 2] for i in range(len(run) - 1))
    return out


# ---------------------------------------------------------------------------
# main app.asar translation
# ---------------------------------------------------------------------------

LITERAL_SKIP_FILES = {'dist/electron/174.js', 'dist/electron/188.js'}


def literal_target(name):
    if not name.startswith('dist/electron/') or name.startswith('dist/electron/static/'):
        return False
    if name in LITERAL_SKIP_FILES:
        return False
    base = name.rsplit('/', 1)[-1]
    if base.startswith('locales-') and base.endswith('.js'):
        return False
    return base.rsplit('.', 1)[-1] in ('js', 'html')


def try_text(arc, name):
    try:
        return arc.text(name)
    except (KeyError, UnicodeDecodeError):
        return None


def map_skip_positions(arc, lits):
    """skip.json lists string positions (in the Windows 7.0.5 files) that must
    stay Chinese because they are compared with data from the phone/server.
    Find each one in the Mac file: code shifts by the same amount over a
    region, so pick the shift at which the most neighbouring skip positions
    land on a Chinese string at once. literals.json (Windows positions too,
    but not always from the same file state) gives a first estimate."""
    raw = load_data('skip.json')
    anchors = collections.defaultdict(list)
    for key, occ in lits.items():
        skey = source_form(key)
        for o in occ:
            anchors[o['f']].append((o['i'] + 1, o.get('q', '"') + skey))
    # a quote followed by Chinese within its first few characters ("1周", ". 开启…")
    string_start = re.compile(r'(?<!\\)[%s](?=(?:\\[nrt]|[^%s\\\n]){0,6}?%s)' % (QUOTES, QUOTES, CJK.pattern))
    mapped = {}
    total = found = 0
    for fn, positions in raw.items():
        total += len(positions)
        t = try_text(arc, fn)
        if t is None:
            continue
        starts = [m.end() for m in string_start.finditer(t)]
        anc = sorted(anchors.get(fn, []))
        where = {}
        # candidate shifts: every Chinese string start near the unshifted
        # position or near the anchor estimate, with its distance from the estimate
        cand = {}
        for p in positions:
            votes = collections.Counter()
            for w, needle in sorted(anc, key=lambda a: abs(a[0] - p))[:12]:
                if needle not in where:
                    where[needle] = [m.start() + 1 for m in re.finditer(re.escape(needle), t)]
                for pos in where[needle]:
                    votes[pos - w] += 1
            guess = votes.most_common(1)[0][0] if votes else 0
            shifts = {}
            for centre in {0, guess}:
                lo = bisect.bisect_left(starts, p + centre - 400)
                hi = bisect.bisect_right(starts, p + centre + 400)
                for c in starts[lo:hi]:
                    shifts[c - p] = abs(c - p - guess)
            cand[p] = shifts
        out = set()
        for p, shifts in cand.items():
            if not shifts:
                continue
            support = collections.Counter()
            for q in positions:
                if q != p and abs(q - p) <= 40000:
                    support.update(d for d in shifts if d in cand[q])
            # many files are unchanged from Windows, so an exact hit wins ties
            best = max(shifts, key=lambda d: (support[d], d == 0, -shifts[d]))
            # a lone position with no neighbour to confirm it must sit close to the estimate
            if support[best] or shifts[best] <= 64:
                out.add(p + best)
                found += 1
        mapped[fn] = out
    return mapped, found, total


def patch_regions(arc, patches):
    """Where a patch with Chinese in it matches vivo's original code, the
    Windows pipeline left that code untranslated so the patch could rewrite
    the whole expression. Return those regions so literals stay out of them."""
    regions = collections.defaultdict(list)
    for p in patches:
        if not CJK.search(p['old']):
            continue
        t = try_text(arc, p['file'])
        if t is None or t.count(p['old']) != p.get('expect', 1):
            continue
        st = 0
        while True:
            i = t.find(p['old'], st)
            if i < 0:
                break
            regions[p['file']].append((i, i + len(p['old'])))
            st = i + 1
    return {fn: sorted(r) for fn, r in regions.items()}


def translate_literals(arc, patches):
    """Port of apply_literals.py: every quoted occurrence of a dictionary key
    in the UI bundles becomes its English text."""
    lits = load_data('literals.json')
    mapping = {}
    for fn in sorted(os.listdir(DATA)):
        if fn.startswith('map_en') and fn.endswith('.json'):
            mapping.update(load_data(fn))
    allow_files = load_data('map_files.json')
    skip, skip_found, skip_total = map_skip_positions(arc, lits)
    regions = patch_regions(arc, patches)
    starts = {fn: [a for a, b in rs] for fn, rs in regions.items()}
    longest = {fn: max(b - a for a, b in rs) for fn, rs in regions.items()}

    def in_patch(fn, s, e):
        # does [s, e) overlap any region [a, b)?
        rs = regions.get(fn)
        if not rs:
            return False
        i = bisect.bisect_left(starts[fn], e) - 1
        while i >= 0 and rs[i][0] > s - longest[fn]:
            if rs[i][1] > s:
                return True
            i -= 1
        return False

    ui_files = [n for n in sorted(arc.entries) if literal_target(n) and try_text(arc, n) is not None]
    index = {n: bigrams(arc.text(n)) for n in ui_files}

    norm_index = {}
    for k in lits:
        nk = norm_key(k)
        if nk not in norm_index or len(k) < len(norm_index[nk]):
            norm_index[nk] = k

    spans = collections.defaultdict(list)
    seen = set()
    hits = collections.Counter()
    pad = r'(?:[ \t\r\n]|\\[nrt])*'

    def take(fn, s, e, new, closed, raw, lit):
        seen.add((fn, s))
        if s in skip.get(fn, ()) or in_patch(fn, s, e):
            return
        spans[fn].append((s, e, new, closed, raw))
        hits[lit] += 1

    def candidates(names, skey):
        need = bigrams(skey)
        return [n for n in names if (n not in index or need <= index[n]) and skey in (try_text(arc, n) or '')]

    def scan(names, skey, en, lit, closed):
        for fn in names:
            t = arc.text(fn)
            for q in QUOTES:
                if re.search(r'(?<!\\)' + re.escape(q), skey):
                    continue
                needle = q + skey + q if closed else q + skey
                st = 0
                while True:
                    i = t.find(needle, st)
                    if i < 0:
                        break
                    st = i + 1
                    if (fn, i + 1) not in seen:
                        take(fn, i + 1, i + 1 + len(skey), en, closed, False, lit)

    def scan_padded(names, skey, en, lit):
        for fn in names:
            t = arc.text(fn)
            for q in QUOTES:
                if re.search(r'(?<!\\)' + re.escape(q), skey):
                    continue
                pat = re.compile(re.escape(q) + '(' + pad + ')' + re.escape(skey) + '(' + pad + ')' + re.escape(q))
                for m in pat.finditer(t):
                    if m.start() == 0 or t[m.start() - 1] == '\\':
                        continue
                    s, e = m.start() + 1, m.end() - 1
                    if (fn, s) in seen or (m.group(1) == '' and m.group(2) == ''):
                        continue
                    take(fn, s, e, m.group(1) + esc(en, skey, q) + m.group(2), True, True, lit)

    for lit, en in mapping.items():
        allow = set(allow_files.get(lit, [])) or None
        key = lit if lit in lits else norm_index.get(norm_key(lit), lit)
        skey = source_form(key)
        # 1) occurrences recorded on Windows, where they still line up
        for o in lits.get(key, []):
            fn = o['f']
            if allow and fn.rsplit('/', 1)[-1] not in allow:
                continue
            t = try_text(arc, fn)
            s = o['i'] + 1
            e = s + len(skey)
            if t is None or (fn, s) in seen:
                continue
            if s - 1 >= len(t) or t[s - 1] not in QUOTES or t[s:e] != skey or t[e:e + 1] not in QUOTES:
                continue
            take(fn, s, e, en, True, False, lit)
        # 2) search by content
        targets = sorted('dist/electron/' + b for b in allow) if allow else ui_files
        targets = candidates([n for n in targets if try_text(arc, n) is not None], skey)
        scan_padded(targets, skey, en, lit)
        scan(targets, skey, en, lit, True)
        if hits[lit] == 0 and len(skey) >= 4:
            scan(targets, skey, en, lit, False)

    changed = {}
    dropped = 0
    for fn, sp in spans.items():
        sp.sort(key=lambda x: (x[0], -x[1]))
        keep = []
        for cur in sp:
            if keep and cur[0] < keep[-1][1]:
                # inside a longer literal already being replaced
                if cur[1] > keep[-1][1]:
                    dropped += 1
                continue
            keep.append(cur)
        t = arc.text(fn)
        out = []
        prev = 0
        for s, e, new, closed, raw in keep:
            if t[s - 1] not in QUOTES or (closed and t[e] not in QUOTES):
                dropped += 1
                continue
            out.append(t[prev:s])
            out.append(new if raw else esc(new, t[s:e], t[s - 1]))
            prev = e
        out.append(t[prev:])
        changed[fn] = ''.join(out)

    stats = {
        'keys': len(mapping),
        'keys_used': sum(1 for k in mapping if hits[k]),
        'replacements': sum(hits.values()) - dropped,
        'protected': '%d/%d' % (skip_found, skip_total),
    }
    return changed, stats


JS_STRING = re.compile(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'')
ONE_LETTER = re.compile(r'(?<![\w$.])[A-Za-z](?![\w$])')


def code_letters(s):
    """One-letter identifiers in a code fragment, outside quoted strings."""
    masked = JS_STRING.sub(lambda m: ' ' * len(m.group(0)), s)
    return [m for m in ONE_LETTER.finditer(masked)]


def loose_replace(t, old, new, expect):
    """The minifier often renames one-letter variables between builds
    (e.step on Windows, t.step on Mac). Match `old` with those letters as
    consistent wildcards and carry the same renames into `new`."""
    letters = code_letters(old)
    if not letters:
        return None
    pat, pos, seen = [], 0, set()
    for m in letters:
        pat.append(re.escape(old[pos:m.start()]))
        name = 'v' + m.group(0)
        pat.append('(?P=%s)' % name if name in seen else '(?<![\\w$])(?P<%s>[A-Za-z])(?![\\w$])' % name)
        seen.add(name)
        pos = m.end()
    pat.append(re.escape(old[pos:]))
    found = list(re.finditer(''.join(pat), t))
    if len(found) != expect:
        return None
    out, prev = [], 0
    for m in found:
        rename = {k[1:]: v for k, v in m.groupdict().items()}
        if len(set(rename.values())) != len(rename):
            return None
        rep, last = [], 0
        for lm in code_letters(new):
            # a lone English word ("a", "I") between spaces is text, not code
            text_word = new[lm.start() - 1:lm.start()] == ' ' and new[lm.end():lm.end() + 1] == ' '
            rep.append(new[last:lm.start()])
            rep.append(lm.group(0) if text_word else rename.get(lm.group(0), lm.group(0)))
            last = lm.end()
        rep.append(new[last:])
        out.append(t[prev:m.start()])
        out.append(''.join(rep))
        prev = m.end()
    out.append(t[prev:])
    return ''.join(out)


def apply_patches(patches, get_text, set_text):
    """Apply exact old -> new rewrites; skip any whose match count differs."""
    applied = already = 0
    missed = []
    for p in patches:
        t = get_text(p['file'])
        if t is None:
            missed.append((p, -1))
            continue
        count = t.count(p['old'])
        if count == 0 and p['new'] in t:
            already += 1
            continue
        if count == 0:
            new = loose_replace(t, p['old'], p['new'], p.get('expect', 1))
            if new is None:
                missed.append((p, 0))
            else:
                set_text(p['file'], new)
                applied += 1
            continue
        if count != p.get('expect', 1):
            missed.append((p, count))
            continue
        set_text(p['file'], t.replace(p['old'], p['new']))
        applied += 1
    return applied, already, missed


LOCALE_MAP = re.compile(r'\{("\./[A-Za-z]+\.json":\d+,?)+\}')
LOCALE_ITEM = re.compile(r'"(\./[A-Za-z]+\.json)":(\d+)')


def locale_module(mid):
    return re.compile(r"(?<![\w$])" + re.escape(mid)
                      + r":function\(e\)\{e\.exports=JSON\.parse\('((?:[^'\\]|\\.)*)'\)\}")


def locale_modules(text):
    best = None
    for m in LOCALE_MAP.finditer(text):
        items = LOCALE_ITEM.findall(m.group(0))
        if best is None or len(items) > len(best):
            best = items
    if not best:
        raise Fail('locale module table not found in locales-en_US.js')
    return {fname[2:-5]: mid for fname, mid in best}


def merge_locales(mac_text, ref_text):
    """Add the English keys the Windows project injected (missing from vivo's
    own en_US file) to the Mac en_US locale. Module ids differ between the
    builds, so modules are matched by namespace."""
    mac_ids = locale_modules(mac_text)
    ref_ids = locale_modules(ref_text)
    added = 0
    for ns, mid in mac_ids.items():
        if ns not in ref_ids:
            continue
        rm = locale_module(ref_ids[ns]).search(ref_text)
        mm = locale_module(mid).search(mac_text)
        if not rm or not mm:
            continue
        ref = json.loads(unescape_js(rm.group(1)))
        cur = json.loads(unescape_js(mm.group(1)))
        extra = {k: v for k, v in ref.items() if k not in cur}
        if not extra:
            continue
        cur.update(extra)
        payload = escape_js(json.dumps(cur, ensure_ascii=False, separators=(',', ':')))
        mac_text = mac_text[:mm.start(1)] + payload + mac_text[mm.end(1):]
        check = json.loads(unescape_js(locale_module(mid).search(mac_text).group(1)))
        if len(check) != len(cur):
            raise Fail('locale merge check failed for ' + ns)
        added += len(extra)
    return mac_text, added


# zh_CN -> en_US as the default language (same-length edits from build_asar.py)
DEFAULT_LOCALE_EDITS = []
for _fn, _v, _f in (('renderer.js', 'n', 'o'), ('child-window.js', 'l', 'c'), ('module-share-preview.js', 'l', 'c')):
    DEFAULT_LOCALE_EDITS += [
        {'file': 'dist/electron/' + _fn, 'old': 'if(!%s)return"zh_CN"' % _v, 'new': 'if(!%s)return"en_US"' % _v},
        {'file': 'dist/electron/' + _fn, 'old': '%s?%s():"zh_CN"' % (_v, _f), 'new': '%s?%s():"en_US"' % (_v, _f)},
        {'file': 'dist/electron/' + _fn, 'old': '%s?"en_US":"zh_CN"' % _v, 'new': '%s?"en_US":"en_US"' % _v},
    ]

# CSS overrides from mk_css_patch.py: (chunk, marker, selector that must exist, css)
CSS_JOBS = [
    ('130', 'batch22c', 'data-v-f20bebaa', (
        '\n/* batch22c: Go to date labels wider than their columns */\n'
        '.dialog-middle[data-v-f20bebaa] .vivo-dialog-body .item-content .textCss{font-size:15px}\n'
        '.dialog-middle[data-v-f20bebaa] .vivo-dialog-body .item-content .year,'
        '.dialog-middle[data-v-f20bebaa] .vivo-dialog-body .item-content .month,'
        '.dialog-middle[data-v-f20bebaa] .vivo-dialog-body .item-content .day{white-space:nowrap}\n')),
    ('8', 'batch29reminder', 'reminder_list-item_3yAmE', (
        '\n/* batch29reminder: two-line reminder labels in a fixed 40px item */\n'
        '.reminder_list-item_3yAmE{height:auto;min-height:40px}\n'
        '.reminder_list-item_3yAmE .list-item-title{white-space:nowrap}\n')),
    ('14', 'batch29margin', 'slider-margin[data-v-014f64e8]', (
        '\n/* batch29margin: "Large" (page margin) letters stacked vertically */\n'
        '.slider-margin[data-v-014f64e8] .la-slider__marks-text{width:max-content;white-space:nowrap}\n')),
    ('117', 'batch29margin', 'slider-margin[data-v-014f64e8]', (
        '\n/* batch29margin: "Large" (page margin) letters stacked vertically */\n'
        '.slider-margin[data-v-014f64e8] .la-slider__marks-text{width:max-content;white-space:nowrap}\n')),
    ('137', 'batch29album', 'album-left-bar-container[data-v-97718154]', (
        '\n/* batch29album: "Recently deleted" broken mid-word in the 180px rail */\n'
        '.album-left-bar-container[data-v-97718154]{width:210px}\n'
        '.album-left-bar-container .add-wrap[data-v-97718154]{width:210px}\n'
        '.album-left-bar-container .add-wrap .add-box[data-v-97718154]{width:170px}\n'
        '.album-left-bar-container .album-container-menu[data-v-97718154]{width:210px}\n'
        '.back-box[data-v-97718154]{width:210px}\n'
        '.link .folder-name[data-v-97718154]{display:block;min-width:0;white-space:nowrap;'
        'overflow:hidden;text-overflow:ellipsis;word-break:normal}\n')),
    ('118', 'batch42recorder', 'data-v-fc27b3a4', (
        '\n/* batch42recorder: sync settings tab strip, "Recorder" hangs outside the pill */\n'
        '[data-v-fc27b3a4] .tab-has-recorder .vivo-tab-nav{width:272px!important}\n'
        '[data-v-fc27b3a4] .tab-has-recorder .vivo-tab-nav .vivo-tab-nav-item:last-child{'
        '-webkit-box-flex:78px!important;-webkit-flex:78px 0 0!important;'
        '-ms-flex:78px 0 0!important;flex:78px 0 0!important;white-space:nowrap}\n')),
]


def translate_main(arc):
    """Return ({name: new text}, {name: added bytes})."""
    changed = {}

    def get(fn):
        return changed[fn] if fn in changed else try_text(arc, fn)

    def put(fn, text):
        changed[fn] = text

    step('Merging English locale keys')
    loc = 'dist/electron/locales-en_US.js'
    with open(os.path.join(DATA, 'locales-en_US.js.new'), encoding='utf-8') as fh:
        merged, count = merge_locales(arc.text(loc), fh.read())
    if count:
        changed[loc] = merged
    note('%d keys added' % count)

    patches = load_data('patches.json')
    step('Translating hardcoded Chinese strings (takes a minute)')
    lit_changed, stats = translate_literals(arc, patches)
    changed.update(lit_changed)
    note('%d of %d dictionary entries found, %d strings replaced in %d files'
         % (stats['keys_used'], stats['keys'], stats['replacements'], len(lit_changed)))
    note('server-compared strings kept in Chinese: %s located' % stats['protected'])

    step('Applying exact patches')
    applied, already, missed = apply_patches(patches, get, put)
    note('%d applied, %d already English, %d skipped (code differs on the Mac build)'
         % (applied, already, len(missed)))

    # a translation must never put a real newline into a one-line minified bundle
    for fn, t in list(changed.items()):
        base = fn.rsplit('/', 1)[-1]
        if not fn.endswith('.js') or '/static/' in fn or base.startswith('locales-'):
            continue
        orig = arc.text(fn)
        if '\n' not in orig and '\r' not in orig and ('\n' in t or '\r' in t):
            changed[fn] = t.replace('\r\n', '\\n').replace('\n', '\\n').replace('\r', '\\r')

    step('Switching the default language to English')
    applied, already, missed = apply_patches(DEFAULT_LOCALE_EDITS, get, put)
    note('%d of %d switches set' % (applied + already, len(DEFAULT_LOCALE_EDITS)))
    if applied + already < 3:
        raise Fail('could not find the default-language code in renderer.js; '
                   'this app version is not supported')

    step('Layout fixes for longer English labels')
    done = 0
    for chunk, mark, selector, css in CSS_JOBS:
        pat = re.compile(r'dist/electron/%s\.[0-9a-f]{8}\.css' % chunk)
        for name in arc.entries:
            if pat.fullmatch(name):
                t = get(name)
                if t and selector in t and mark not in t:
                    changed[name] = t + css
                    done += 1
    note('%d of %d CSS fixes applied' % (done, len(CSS_JOBS)))

    added = {}
    # TinyMCE asks for en_US_in outside the export build; only zh_CN_in ships
    with open(os.path.join(DATA, 'tinymce_langs_en_US_in.js'), 'rb') as fh:
        tiny = fh.read()
    for name in arc.entries:
        m = re.fullmatch(r'(dist/electron/static/tinymce/[^/]+/langs/)zh_CN_in\.js', name)
        if m and m.group(1) + 'en_US_in.js' not in arc.entries:
            added[m.group(1) + 'en_US_in.js'] = tiny
    return changed, added


def node_check(arc, modified):
    """Syntax-check changed JS with node when it is installed (optional)."""
    node = shutil.which('node')
    if not node:
        return
    step('Syntax-checking changed JavaScript with node')
    bad = []
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, 'check.js')
        for name, data in modified.items():
            if not name.endswith('.js'):
                continue
            with open(path, 'wb') as fh:
                fh.write(data)
            if subprocess.run([node, '--check', path], capture_output=True).returncode == 0:
                continue
            with open(path, 'wb') as fh:
                fh.write(arc.read(name))
            if subprocess.run([node, '--check', path], capture_output=True).returncode == 0:
                bad.append(name)
    if bad:
        raise Fail('the patched JavaScript has syntax errors in: ' + ', '.join(bad))
    note('OK')


def build_main(src_path, dst_path, marker):
    arc = Asar(src_path)
    try:
        changed, added = translate_main(arc)
        modified = {n: t.encode('utf-8') for n, t in changed.items()}
        node_check(arc, modified)
        added[MARKER] = json.dumps(marker, indent=1).encode('utf-8')
        step('Writing the English app.asar')
        write_asar(arc, modified, added, dst_path)
        note('%d files changed, %d added, archive verified' % (len(modified), len(added)))
    finally:
        arc.close()


def build_vc(src_path, dst_path, marker):
    arc = Asar(src_path)
    try:
        changed = {}

        def get(fn):
            return changed[fn] if fn in changed else try_text(arc, fn)

        def put(fn, text):
            changed[fn] = text

        applied, already, missed = apply_patches(load_data('patches_vc.json'), get, put)
        note('%d applied, %d already English, %d skipped' % (applied, already, len(missed)))
        modified = {n: t.encode('utf-8') for n, t in changed.items()}
        node_check(arc, modified)
        write_asar(arc, modified, {MARKER: json.dumps(marker, indent=1).encode('utf-8')}, dst_path)
    finally:
        arc.close()


# ---------------------------------------------------------------------------
# install / restore
# ---------------------------------------------------------------------------

def app_paths(app):
    res = os.path.join(app, 'Contents', 'Resources')
    screen = os.path.join(res, 'vivoScreen', 'vivoScreen.app')
    return {
        'main': os.path.join(res, 'app.asar'),
        'vc': os.path.join(res, 'vivoControl', 'vcontrol.app', 'Contents', 'Resources', 'app.asar'),
        'screen_app': screen,
        'screen_bin': os.path.join(screen, 'Contents', 'MacOS', 'vivoScreen'),
        'screen_sig': os.path.join(screen, 'Contents', '_CodeSignature', 'CodeResources'),
        'config': os.path.join(SUPPORT, 'config.ini'),
    }


FUSE_SENTINEL = b'dL7pKGdnNz796PbbjQWNKmHXBZaB9tsX'


def asar_integrity_enforced(app):
    """Electron fuse 4 (EnableEmbeddedAsarIntegrityValidation). It is off in
    7.0.6; if vivo turns it on, a modified app.asar would refuse to load."""
    fw = os.path.join(app, 'Contents', 'Frameworks', 'Electron Framework.framework', 'Electron Framework')
    try:
        with open(fw, 'rb') as fh, mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            i = mm.find(FUSE_SENTINEL)
            if i < 0:
                return False
            at = i + len(FUSE_SENTINEL)
            fuses = mm[at + 2:at + 2 + mm[at + 1]]
    except (OSError, ValueError):
        return False
    return fuses[4:5] == b'1'


def check_app(app, force):
    plist = os.path.join(app, 'Contents', 'Info.plist')
    if not os.path.exists(plist):
        raise Fail('vivo PC Suite not found at %s (use --app to point at pcsuite.app)' % app)
    with open(plist, 'rb') as fh:
        info = plistlib.load(fh)
    if info.get('CFBundleIdentifier') != BUNDLE_ID:
        raise Fail('%s is not vivo PC Suite (bundle id %s)' % (app, info.get('CFBundleIdentifier')))
    if asar_integrity_enforced(app):
        raise Fail('this vivo PC Suite version verifies app.asar against its code signature; '
                   'the patcher does not support it')
    cfg = os.path.join(app, 'Contents', 'Resources', 'build-config.json')
    if os.path.exists(cfg):
        with open(cfg, encoding='utf-8') as fh:
            if json.load(fh).get('IS_EXPORT') and not force:
                raise Fail('this is the global (export) build, which is already in English')
    return info.get('CFBundleShortVersionString', '?')


def check_writable(directory):
    probe = os.path.join(directory, '.english-patch-probe')
    try:
        with open(probe, 'wb') as fh:
            fh.write(b'ok')
        os.remove(probe)
    except PermissionError as exc:
        if exc.errno == 1:  # EPERM: App Management protection
            raise Fail(APP_MANAGEMENT_HELP)
        raise Fail('no permission to write %s; run again with sudo' % directory)


def load_state():
    try:
        with open(STATE, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {'items': {}}


def save_state(state):
    os.makedirs(BACKUP, exist_ok=True)
    tmp = STATE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(state, fh, indent=1)
    os.replace(tmp, STATE)


def copy_over(src, dst):
    """Copy src onto dst via a temp file + rename (never overwrite in place:
    macOS caches code signatures per file)."""
    tmp = dst + '.english-tmp'
    shutil.copyfile(src, tmp)
    if os.path.exists(dst):
        shutil.copymode(dst, tmp)
    os.replace(tmp, dst)


def prepare_source(key, installed, state):
    """Return the backup copy of vivo's original archive to build from."""
    bpath = os.path.join(BACKUP, key + '.asar')
    arc = Asar(installed)
    mark = arc.marker()
    arc.close()
    rec = state['items'].get(key)
    if mark is None:
        # installed file is vivo's original (fresh install or app update)
        digest = file_sha256(installed)
        if not (rec and rec.get('sha256') == digest and os.path.exists(bpath)):
            note('backing up %s' % installed)
            copy_over(installed, bpath)
            state['items'][key] = {'sha256': digest, 'backup': bpath}
        return bpath, digest
    if not rec or rec.get('sha256') != mark.get('source_sha256') or not os.path.exists(bpath):
        raise Fail('%s is already patched but its original backup is missing. Reinstall '
                   'vivo PC Suite, then run the patcher again.' % installed)
    return bpath, rec['sha256']


def dry_source(key, installed, state):
    arc = Asar(installed)
    mark = arc.marker()
    arc.close()
    if mark is None:
        return installed, file_sha256(installed)
    rec = state['items'].get(key)
    if not rec or not os.path.exists(rec.get('backup', '')):
        raise Fail('%s is already patched and no backup was found' % installed)
    return rec['backup'], rec['sha256']


def make_marker(version, source_sha):
    return {'patcher': PATCHER_VERSION, 'project': PROJECT, 'app_version': version,
            'source_sha256': source_sha,
            'built': datetime.datetime.now().isoformat(timespec='seconds')}


def main_pids(app):
    exe = os.path.join(app, 'Contents', 'MacOS', 'pcsuite')
    out = subprocess.run(['pgrep', '-f', '^' + re.escape(exe)], capture_output=True, text=True).stdout
    return [int(x) for x in out.split() if int(x) != os.getpid()]


def wait_gone(app, seconds):
    end = time.time() + seconds
    while time.time() < end:
        if not main_pids(app):
            return True
        time.sleep(0.5)
    return not main_pids(app)


def quit_app(app, assume_yes):
    pids = main_pids(app)
    if not pids:
        return False
    if not confirm('vivo PC Suite is running and will be closed (and reopened after). Continue?', assume_yes):
        raise Fail('cancelled, nothing was changed')
    step('Closing vivo PC Suite')
    # Electron treats SIGTERM as a normal quit (before-quit / will-quit run)
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    if not wait_gone(app, 20):
        raise Fail('vivo PC Suite did not close. Quit it from its menu-bar icon and run again.')
    time.sleep(1)
    return True


def launch(app):
    step('Starting vivo PC Suite')
    subprocess.run(['open', app])


def set_config_language(path, state):
    if not os.path.exists(path):
        note('config.ini not found yet (start the app once); skipped')
        return
    with open(path, encoding='utf-8', errors='surrogateescape') as fh:
        text = fh.read()
    new = text
    if re.search(r'(?m)^LanguageTag=', new):
        new = re.sub(r'(?m)^LanguageTag=.*$', 'LanguageTag=en_US', new)
    elif '[PCSuite]' in new:
        new = new.replace('[PCSuite]', '[PCSuite]\nLanguageTag=en_US', 1)
    new = re.sub(r'(?m)^LanguageID=.*$', 'LanguageID=1033', new)
    if new == text:
        note('config.ini already English')
        return
    bpath = os.path.join(BACKUP, 'config.ini')
    if 'config' not in state['items']:
        shutil.copyfile(path, bpath)
        state['items']['config'] = {'backup': bpath}
    with open(path, 'w', encoding='utf-8', errors='surrogateescape') as fh:
        fh.write(new)
    note('config.ini set to en_US')


MIRROR_OLD = b'zh-CN\x00en-US'
MIRROR_NEW = b'en-US\x00en-US'


def patch_mirror(paths, state):
    """Phone Mirroring (Qt) boots in its embedded default language. Flip it
    to en-US and re-sign the app ad hoc (macOS kills binaries whose bytes no
    longer match their signature)."""
    exe = paths['screen_bin']
    if not os.path.exists(exe):
        note('vivoScreen.app not found; skipped')
        return
    with open(exe, 'rb') as fh:
        data = fh.read()
    if data.count(b'zh-CN') == 0 and MIRROR_NEW in data:
        note('already English')
        return
    pos = data.find(MIRROR_OLD)
    if data.count(b'zh-CN') != 1 or pos < 0 or b'LanguageManager' not in data[max(0, pos - 200):pos]:
        note('language setting not found in this vivoScreen build; skipped')
        return
    if 'mirror' not in state['items']:
        os.makedirs(os.path.join(BACKUP, 'vivoScreen'), exist_ok=True)
        rec = {'bin': os.path.join(BACKUP, 'vivoScreen', 'vivoScreen'),
               'sig': os.path.join(BACKUP, 'vivoScreen', 'CodeResources')}
        shutil.copyfile(exe, rec['bin'])
        shutil.copyfile(paths['screen_sig'], rec['sig'])
        state['items']['mirror'] = rec
        save_state(state)
    tmp = exe + '.english-tmp'
    with open(tmp, 'wb') as fh:
        fh.write(data.replace(MIRROR_OLD, MIRROR_NEW))
    shutil.copymode(exe, tmp)
    os.replace(tmp, exe)
    sign = subprocess.run(['codesign', '--force', '--sign', '-', '--preserve-metadata=entitlements,flags,runtime',
                           paths['screen_app']], capture_output=True, text=True)
    if sign.returncode != 0:
        restore_mirror(paths, state['items']['mirror'])
        raise Fail('re-signing vivoScreen.app failed, original put back:\n' + sign.stderr)
    note('Phone Mirroring set to en-US (re-signed ad hoc)')


def restore_mirror(paths, rec):
    copy_over(rec['bin'], paths['screen_bin'])
    copy_over(rec['sig'], paths['screen_sig'])


def cmd_apply(args):
    app = os.path.abspath(args.app)
    version = check_app(app, args.force)
    paths = app_paths(app)
    has_vc = os.path.exists(paths['vc'])
    say('vivo PC Suite %s at %s' % (version, app))
    state = load_state()
    if state.get('app_version') != version:
        state = {'app_version': version, 'items': {}}

    if args.dry_run:
        out = os.path.abspath(args.out or tempfile.mkdtemp(prefix='vivo-english-'))
        os.makedirs(out, exist_ok=True)
        src, digest = dry_source('main', paths['main'], state)
        build_main(src, os.path.join(out, 'app.asar'), make_marker(version, digest))
        if has_vc:
            step('Building the English Remote PC window')
            src, digest = dry_source('vc', paths['vc'], state)
            build_vc(src, os.path.join(out, 'vcontrol-app.asar'), make_marker(version, digest))
        say('\nDry run finished. Nothing installed; patched archives are in ' + out)
        return 0

    check_writable(os.path.dirname(paths['main']))
    if has_vc:
        check_writable(os.path.dirname(paths['vc']))
    os.makedirs(BACKUP, exist_ok=True)
    if shutil.disk_usage(BACKUP).free < 1.5e9:
        raise Fail('need about 1.5 GB of free disk space')

    tmp_main = paths['main'] + '.english-tmp'
    tmp_vc = paths['vc'] + '.english-tmp'
    try:
        step('Backing up the originals to ' + BACKUP)
        main_src, main_sha = prepare_source('main', paths['main'], state)
        vc_src = vc_sha = None
        if has_vc:
            vc_src, vc_sha = prepare_source('vc', paths['vc'], state)
        save_state(state)

        build_main(main_src, tmp_main, make_marker(version, main_sha))
        if has_vc:
            step('Building the English Remote PC window')
            build_vc(vc_src, tmp_vc, make_marker(version, vc_sha))

        was_running = quit_app(app, args.yes)
        step('Installing')
        os.replace(tmp_main, paths['main'])
        if has_vc:
            os.replace(tmp_vc, paths['vc'])
        note('English app.asar installed')
        if args.mirror:
            step('Phone Mirroring language')
            patch_mirror(paths, state)
        step('Language setting')
        set_config_language(paths['config'], state)
        save_state(state)
    finally:
        for tmp in (tmp_main, tmp_vc):
            if os.path.exists(tmp):
                os.remove(tmp)

    if not args.no_launch and (was_running or args.yes or confirm('Start vivo PC Suite now?', False)):
        launch(app)
    say('\nDone. vivo PC Suite is now in English.')
    say('To undo:  python3 "%s" --restore' % os.path.abspath(__file__))
    return 0


def cmd_restore(args):
    app = os.path.abspath(args.app)
    version = check_app(app, True)
    paths = app_paths(app)
    state = load_state()
    items = state.get('items') or {}
    if not items:
        raise Fail('no backup found in %s; nothing to restore' % BACKUP)
    if state.get('app_version') != version:
        raise Fail('the backups are for version %s but %s is installed; the update already '
                   'replaced the patched files' % (state.get('app_version'), version))
    check_writable(os.path.dirname(paths['main']))
    was_running = quit_app(app, args.yes)
    step('Restoring originals')
    for key in ('main', 'vc'):
        rec = items.get(key)
        if not rec or not os.path.exists(paths[key]):
            continue
        arc = Asar(paths[key])
        mark = arc.marker()
        arc.close()
        if mark is None:
            note('%s is already the original' % paths[key])
        elif not os.path.exists(rec['backup']) or file_sha256(rec['backup']) != rec['sha256']:
            raise Fail('backup %s is missing or damaged' % rec['backup'])
        else:
            copy_over(rec['backup'], paths[key])
            note('restored ' + paths[key])
    if 'mirror' in items:
        restore_mirror(paths, items['mirror'])
        note('restored vivoScreen.app')
        del items['mirror']
    if 'config' in items and os.path.exists(items['config']['backup']):
        shutil.copyfile(items['config']['backup'], paths['config'])
        note('restored config.ini')
        del items['config']
    save_state(state)
    if was_running and not args.no_launch:
        launch(app)
    say('\nDone. vivo PC Suite is back to the original (Chinese) version.')
    say('Backups are kept in %s (about 400 MB); delete that folder if you no longer need it.' % BACKUP)
    return 0


def main():
    ap = argparse.ArgumentParser(description='Translate vivo PC Suite (China build) to English on macOS.')
    ap.add_argument('--app', default=DEFAULT_APP, help='path to pcsuite.app (default: %(default)s)')
    ap.add_argument('--restore', action='store_true', help='put the original Chinese files back')
    ap.add_argument('--mirror', action='store_true',
                    help='also switch Phone Mirroring (vivoScreen.app) to English; this re-signs it ad hoc')
    ap.add_argument('--dry-run', action='store_true', help='build the patched files without installing them')
    ap.add_argument('--out', help='with --dry-run: folder for the patched files')
    ap.add_argument('--no-launch', action='store_true', help='do not start vivo PC Suite afterwards')
    ap.add_argument('-y', '--yes', action='store_true', help='do not ask before closing the app')
    ap.add_argument('--force', action='store_true', help='patch even the export (global) build')
    args = ap.parse_args()
    if sys.platform != 'darwin':
        say('This patcher is for macOS. On Windows use VivoEnglishPatcher.exe from the Releases page.')
        return 1
    if not os.path.exists(os.path.join(DATA, 'patches.json')):
        say('ERROR: translation data not found; keep the mac/ folder inside the repository')
        return 1
    start = time.time()
    try:
        rc = cmd_restore(args) if args.restore else cmd_apply(args)
    except Fail as exc:
        say('\nERROR: %s' % exc)
        return 1
    except KeyboardInterrupt:
        say('\nInterrupted.')
        return 130
    say('(%.0f s)' % (time.time() - start))
    return rc


if __name__ == '__main__':
    sys.exit(main())

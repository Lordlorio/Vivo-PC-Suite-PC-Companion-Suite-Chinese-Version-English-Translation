# -*- coding: utf-8 -*-
"""Cree les CSS surcharges dans patched/dist/electron/ (original + override).

A executer APRES apply_literals.py --apply (qui vide patched/).

Jobs :
- 130.48bfa161.css (batch22c, conserve) : labels EN du Go to date plus larges
  que les colonnes -> wrap sous la pilule 50px -> chevauchement des boutons.
- 8.1ecea9a4.css (batch29reminder) : libelles EN du rappel ("15 minutes
  before"...) sur 2 lignes dans un item de 40px fixe -> chevauchement.
- 14.82fb7103.css + 117.364ece2c.css (batch29margin) : "Large" (Page margin des
  notes) reduit a fit-content disponible ~0 a left:100% -> lettres empilees.
- 137.1d62d6b9.css (batch29album) : "Recently deleted" coupe au milieu des mots
  dans le rail de 180px (word-break:break-all) -> rail 210px + ellipsis.
"""
import json
import os
import struct
import sys

sys.stdout.reconfigure(encoding="utf-8")
ASAR = os.environ.get('PC_ASAR_SRC') or r'E:\Program Files\vivo\_backup_vivo_original_20260930\app.asar'
HERE = os.path.dirname(os.path.abspath(__file__))

OVERRIDE_130 = (
    '\n'
    '/* batch22c: labels EN du Go to date plus larges que les colonnes -> wrap '
    'sous la pilule 50px -> chevauchement des boutons. */\n'
    '.dialog-middle[data-v-f20bebaa] .vivo-dialog-body .item-content .textCss{font-size:15px}\n'
    '.dialog-middle[data-v-f20bebaa] .vivo-dialog-body .item-content .year,'
    '.dialog-middle[data-v-f20bebaa] .vivo-dialog-body .item-content .month,'
    '.dialog-middle[data-v-f20bebaa] .vivo-dialog-body .item-content .day{white-space:nowrap}\n'
)

OVERRIDE_REMINDER = (
    '\n'
    '/* batch29reminder: les libelles EN ("15 minutes before"...) tiennent sur '
    '2 lignes dans un item de 40px fixe -> les lignes se chevauchent. '
    'Le popover passe a 200px (patch 8.js) ; les items grandissent si besoin et '
    'le titre reste sur une ligne. */\n'
    '.reminder_list-item_3yAmE{height:auto;min-height:40px}\n'
    '.reminder_list-item_3yAmE .list-item-title{white-space:nowrap}\n'
)

OVERRIDE_MARGIN = (
    '\n'
    '/* batch29margin: "Large" (Page margin) reduit a fit-content ~0 a '
    'left:100% -> lettres empilees verticalement. Force la largeur '
    'intrinseque et interdit le retour a la ligne. */\n'
    '.slider-margin[data-v-014f64e8] .la-slider__marks-text{width:max-content;white-space:nowrap}\n'
)

OVERRIDE_ALBUM = (
    '\n'
    '/* batch29album: "Recently deleted" coupe au milieu des mots dans le rail '
    'de 180px (word-break:break-all). Rail elargi a 210px, noms d album sur '
    'une ligne avec ellipsis (infobulle JS au survol pour les noms longs). */\n'
    '.album-left-bar-container[data-v-97718154]{width:210px}\n'
    '.album-left-bar-container .add-wrap[data-v-97718154]{width:210px}\n'
    '.album-left-bar-container .add-wrap .add-box[data-v-97718154]{width:170px}\n'
    '.album-left-bar-container .album-container-menu[data-v-97718154]{width:210px}\n'
    '.back-box[data-v-97718154]{width:210px}\n'
    '.link .folder-name[data-v-97718154]{display:block;min-width:0;white-space:nowrap;'
    'overflow:hidden;text-overflow:ellipsis;word-break:normal}\n'
)

JOBS = [
    ('dist/electron/130.48bfa161.css', 'batch22c', OVERRIDE_130),
    ('dist/electron/8.1ecea9a4.css', 'batch29reminder', OVERRIDE_REMINDER),
    ('dist/electron/14.82fb7103.css', 'batch29margin', OVERRIDE_MARGIN),
    ('dist/electron/117.364ece2c.css', 'batch29margin', OVERRIDE_MARGIN),
    ('dist/electron/137.1d62d6b9.css', 'batch29album', OVERRIDE_ALBUM),
]


def main():
    with open(ASAR, 'rb') as fh:
        head = fh.read(64)
        hs = struct.unpack('<I', head[12:16])[0]
        fh.seek(16)
        hdr = json.loads(fh.read(hs).decode('utf-8'))
        base = 12 + ((4 + hs + 3) // 4 * 4)
        node = hdr['files']

        def get(rel):
            n = node
            parts = rel.split('/')
            for part in parts[:-1]:
                n = n[part]['files']
            m = n[parts[-1]]
            fh.seek(base + int(m['offset']))
            return fh.read(int(m['size']))

        for rel, marker, override in JOBS:
            data = get(rel)
            if marker.encode('utf-8') in data:
                print('deja presente, ignore:', rel)
                continue
            css = data.decode('utf-8') + override
            dst = os.path.join(HERE, 'patched', *rel.split('/'))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'w', encoding='utf-8', newline='') as f:
                f.write(css)
            print('ecrit:', dst, len(data), '->', len(css.encode('utf-8')), 'octets')
    return 0


if __name__ == '__main__':
    sys.exit(main())

# -*- coding: utf-8 -*-
"""Passe la fenetre miroir native (vivoScreen.exe, Qt) en anglais.

Constat : l'exe contient UNE occurrence de la langue par defaut embarquee,
juste avant le fallback, dans LanguageManager :
    ...LanguageManager.cpp\\x00\\x00 zh-CN \\x00\\x00\\x00 en-US \\x00\\x00\\x00 cannot load translation {}, switch to load en-US ...
Remplacer ce seul 'zh-CN' par 'en-US' fait demarrer le miroir en anglais
(les ressources EN sont deja dans vivoScreen.rcc, identique des deux cotes).

Usage :
    python patch_vivoscreen_lang.py [chemin_vivoScreen.exe]
Defaut : E:\\Program Files\\vivo\\pcsuite\\vivoScreen\\vivoScreen.exe
Le script fait un backup .old (refuse si le patch est deja applique),
verifie taille inchangee + occurrence unique, puis ecrit.
Note : la signature Authenticode Vivo devient HashMismatch (attendu).
Ne JAMAIS publier l'exe lui-meme (copyright Vivo) : publier ce script.
"""
import hashlib
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")

DEFAULT = r'E:\Program Files\vivo\pcsuite\vivoScreen\vivoScreen.exe'
OLD = b'zh-CN\x00\x00\x00en-US'
NEW = b'en-US\x00\x00\x00en-US'
MARKER = b'LanguageManager'


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    data = open(path, 'rb').read()
    print('fichier : %s (%d octets)' % (path, len(data)))
    if OLD not in data:
        if NEW in data and data.count(b'zh-CN') == 0:
            print('deja en anglais (patch present), rien a faire.')
            return 0
        print('ECHEC : motif de langue par defaut introuvable (version differente ?)')
        return 1
    if data.count(b'zh-CN') != 1:
        print('ECHEC : securite, occurrences zh-CN = %d (attendu 1)' % data.count(b'zh-CN'))
        return 1
    pos = data.find(OLD)
    if MARKER not in data[max(0, pos - 120):pos]:
        print('ECHEC : marqueur LanguageManager absent pres de @%d' % pos)
        return 1
    print('motif trouve @%d, contexte LanguageManager OK' % pos)
    bak = path + '.old'
    if not os.path.exists(bak):
        shutil.copy2(path, bak)
        print('backup : %s' % bak)
    else:
        print('backup deja present : %s' % bak)
    patched = data.replace(OLD, NEW)
    assert len(patched) == len(data), 'taille changee, abandon'
    open(path, 'wb').write(patched)
    print('OK : sha256=%s' % hashlib.sha256(patched).hexdigest().upper())
    print('pense-bete : mettre aussi config.ini sur LanguageID=1033 / LanguageTag=en_US')
    return 0


if __name__ == '__main__':
    sys.exit(main())

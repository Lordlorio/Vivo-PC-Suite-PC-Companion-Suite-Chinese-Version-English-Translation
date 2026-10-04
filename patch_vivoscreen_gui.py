# -*- coding: utf-8 -*-
"""Vivo PC Suite English Patcher (GUI).

Picks the vivo ROOT FOLDER (e.g. E:\\Program Files\\vivo\\pcsuite
or C:\\Program Files (x86)\\pcsuite) plus the translated English app.asar
(provided separately, never on GitHub: too big + copyright), then Apply:
  1. Phone Mirroring (vivoScreen.exe): default locale zh-CN -> en-US (.old backup),
  2. config.ini to 1033/en_US (.old backup),
  3. install the English app.asar into resources\\ (.old backup).
Nothing is written without confirmation. Restore puts the backups back.
Run as administrator, otherwise Windows refuses writes to Program Files.
"""
import hashlib
import os
import shutil
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# ---------------------------------------------------------------------------
# How the Phone Mirroring patch works (read this first).
#
# vivoScreen.exe (Qt, native) picks its UI language from ONE embedded default
# locale string sitting right before its own fallback text:
#     ...LanguageManager.cpp \0\0 "zh-CN" \0\0\0 "en-US" \0\0\0 "cannot load ...
# The English resources already ship inside vivoScreen.rcc, so flipping those
# 4 letters (zh-CN -> en-US) is enough to boot the mirror window in English.
# It occurs exactly once in supported builds (7.0.3/7.0.5); any other count
# means "unknown build, touch nothing".
# Side effect to know: editing the file breaks Vivo's Authenticode signature
# (HashMismatch). That is expected for any post-sign byte edit.
# ---------------------------------------------------------------------------
OLD = b'zh-CN\x00\x00\x00en-US'
NEW = b'en-US\x00\x00\x00en-US'
MARKER = b'LanguageManager'
MIRROR_NAME = 'Phone Mirroring (vivoScreen)'

# ---------------------------------------------------------------------------
# Install-location detection, in order:
#   1. find_via_windows(): Windows' own run-records (MuiCache registry key,
#      same family of data the Control Panel uses) naming vivoScreen.exe /
#      pcsuite.exe, verified to still exist on disk;
#   2. ROOT_CANDIDATES: the three well-known install folders;
#   3. manual Browse... button (never touch an unvalidated folder).
# ---------------------------------------------------------------------------
ROOT_CANDIDATES = [
    r'E:\Program Files\vivo\pcsuite',
    r'C:\Program Files (x86)\pcsuite',
    r'C:\Program Files\vivo\pcsuite',
]
# Next to the tool itself: next to the .py in source mode,
# next to the .exe once packaged (PyInstaller onefile unpacks
# to a temp folder, so __file__ must NOT be used when frozen).
if getattr(sys, 'frozen', False):
    HERE = os.path.dirname(sys.executable)
else:
    HERE = os.path.dirname(os.path.abspath(__file__))
ASAR_CANDIDATES = [
    os.path.join(HERE, 'app.asar'),
    r'C:\Users\Administrator\Downloads\Vivo-PC-Suite-7.0.5-English-Translation\resources\app.asar',
]
CONFIG = os.path.join(os.environ.get('APPDATA', ''), 'pcsuite', 'config.ini')

VIVO_BLUE = '#415FFF'
THEMES = {
    False: {  # light
        'bg': '#F0F0F0', 'fg': '#111111', 'field': '#FFFFFF',
        'btn': '#E1E1E1', 'active': '#D0D0D0', 'logbg': '#FFFFFF',
        'logfg': '#111111', 'logo_fg': '#FFFFFF',
    },
    True: {  # dark
        'bg': '#1E1E1E', 'fg': '#E8E8E8', 'field': '#2D2D2D',
        'btn': '#3A3A3A', 'active': '#4A4A4A', 'logbg': '#252526',
        'logfg': '#E8E8E8', 'logo_fg': '#FFFFFF',
    },
}


def system_is_dark():
    """Follow the user's Windows app theme. Never asks; True = dark."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize') as k:
            v, _ = winreg.QueryValueEx(k, 'AppsUseLightTheme')
            return v == 0
    except OSError:
        return False


def apply_theme(root, dark):
    """Restyle the whole window for light/dark mode."""
    c = THEMES[dark]
    st = ttk.Style(root)
    try:
        st.theme_use('clam')
    except tk.TclError:
        pass
    root.configure(bg=c['bg'])
    st.configure('TFrame', background=c['bg'])
    st.configure('TLabel', background=c['bg'], foreground=c['fg'])
    st.configure('Title.TLabel', background=c['bg'], foreground=c['fg'],
                 font=('Segoe UI', 12, 'bold'))
    st.configure('Sub.TLabel', background=c['bg'], foreground=c['fg'],
                 font=('Segoe UI', 8))
    st.configure('TButton', background=c['btn'], foreground=c['fg'],
                 borderwidth=1, padding=4)
    st.map('TButton', background=[('active', c['active'])])
    st.configure('TEntry', fieldbackground=c['field'], foreground=c['fg'],
                 insertcolor=c['fg'])
    return c


def sha16(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest().upper()[:16]


def describe_exe(path):
    """Return (state, detail): 'zh' = patchable original, 'en' = already
    English, '?' = anything else (unknown build or unreadable file).

    Only the user-friendly verdict is shown; the byte counting stays
    internal. The file date doubles as the "patched on" date because
    patching rewrites the file in place."""
    import datetime
    try:
        st = os.stat(path)
    except OSError:
        return '?', 'file unreadable'
    try:
        with open(path, 'rb') as fh:
            data = fh.read()
    except OSError:
        return '?', 'file unreadable'
    n = data.count(b'zh-CN')
    date = datetime.datetime.fromtimestamp(st.st_mtime).strftime('%Y/%m/%d %H:%M')
    if OLD in data and n == 1:
        return 'zh', '%s: Chinese (original build, file dated %s)' % (MIRROR_NAME, date)
    if OLD not in data and n == 0:
        return 'en', '%s: English (patched on %s)' % (MIRROR_NAME, date)
    return '?', '%s: unknown version (left untouched)' % MIRROR_NAME


def detect_exe(path):
    return describe_exe(path)[0]


def find_via_windows():
    """Ask Windows where Vivo actually runs from.

    Same source family as Control Panel / Programs: executables Windows
    has seen run (MuiCache). Returns a list of existing pcsuite roots,
    most recently relevant first. Pure stdlib (winreg).
    """
    found = []
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r'Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache') as k:
            i = 0
            names = []
            while True:
                try:
                    names.append(winreg.EnumValue(k, i)[0])
                except OSError:
                    break
                i += 1
    except OSError:
        return found
    for name in names:
        low = name.lower()
        if low.endswith(('vivoScreen.exe.friendlyappname'.lower(), 'vivoScreen.exe.applicationcompany'.lower(),
                         'pcsuite.exe.friendlyappname'.lower(), 'pcsuite.exe.applicationcompany'.lower())):
            exe = name.rsplit('.', 1)[0]
            if exe.lower().endswith('vivoscreen.exe'):
                root = os.path.dirname(os.path.dirname(exe))
            else:
                root = os.path.dirname(exe)
            if os.path.exists(os.path.join(root, 'vivoScreen', 'vivoScreen.exe')) and root.lower() not in [f.lower() for f in found]:
                found.append(root)
    return found


def patch_exe(path):
    with open(path, 'rb') as fh:
        data = fh.read()
    n = data.count(b'zh-CN')
    if n != 1 or OLD not in data:
        return False, ('%s: skipped (zh-CN occurrences=%d, pattern %s). '
                       'This is not the expected build (7.0.3/7.0.5), '
                       'please check the root folder.' % (
                           MIRROR_NAME, n, 'found' if OLD in data else 'missing'))
    pos = data.find(OLD)
    if MARKER not in data[max(0, pos - 120):pos]:
        return False, '%s: LanguageManager marker missing @%d, skipped' % (MIRROR_NAME, pos)
    bak = path + '.old'
    if not os.path.exists(bak):
        shutil.copy2(path, bak)
    patched = data.replace(OLD, NEW)
    if len(patched) != len(data):
        return False, '%s: size changed, skipped' % MIRROR_NAME
    with open(path, 'wb') as fh:
        fh.write(patched)
    return True, '%s is now English (sha %s...)' % (MIRROR_NAME, sha16(path))


def patch_config():
    if not os.path.exists(CONFIG):
        return True, 'config.ini not found, skipped'
    with open(CONFIG, 'r', encoding='utf-8', errors='ignore') as fh:
        txt = fh.read()
    if 'LanguageID=1033' in txt and 'LanguageTag=en_US' in txt:
        return True, 'config.ini is already English'
    bak = CONFIG + '.old'
    if not os.path.exists(bak):
        shutil.copy2(CONFIG, bak)
    txt = txt.replace('LanguageID=2052', 'LanguageID=1033')
    txt = txt.replace('LanguageTag=zh_CN', 'LanguageTag=en_US')
    with open(CONFIG, 'w', encoding='utf-8') as fh:
        fh.write(txt)
    return True, 'config.ini set to 1033 / en_US'


def install_asar(src, dst):
    if not os.path.exists(src):
        return False, 'English app.asar not found'
    with open(src, 'rb') as fh:
        head = fh.read(64)
    if len(head) < 16 or int.from_bytes(head[0:4], 'little') != 4:
        return False, 'invalid source file (not an app.asar archive)'
    bak = dst + '.old'
    if os.path.exists(dst) and not os.path.exists(bak):
        shutil.copy2(dst, bak)
    shutil.copy2(src, dst)
    if sha16(src) != sha16(dst):
        return False, 'app.asar: copy mismatch, skipped'
    return True, 'English app.asar installed (sha %s...)' % sha16(dst)


VIVO_PROCESSES = ('pcsuite.exe', 'pcsuite_.exe', 'vivoScreen.exe')


def running_vivo():
    """Names of Vivo processes currently running (stdlib only: tasklist).

    Patching Vivo's files while it runs means locked files and a stale tray,
    so Apply/Restore always close these first and relaunch pcsuite.exe after.
    A graceful close is requested (plain taskkill, no /F); if anything is
    still alive after ~10 s we abort instead of force-killing a transfer."""
    import subprocess
    try:
        out = subprocess.check_output(['tasklist', '/FO', 'CSV', '/NH'],
                                      text=True, errors='ignore',
                                      stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError):
        return []
    running = []
    for line in out.splitlines():
        name = line.split('","')[0].strip().strip('"').lower()
        if name in VIVO_PROCESSES and name not in running:
            running.append(name)
    return running


def close_vivo(say):
    """Ask Vivo processes to quit gracefully. Returns (ok, message)."""
    import subprocess
    import time
    targets = running_vivo()
    if not targets:
        return True, 'Vivo PC Suite is not running'
    say('Closing: ' + ', '.join(targets) + ' ...')
    for name in targets:
        try:
            subprocess.run(['taskkill', '/IM', name], capture_output=True,
                           timeout=15)
        except (OSError, subprocess.SubprocessError):
            pass
    for _ in range(20):
        time.sleep(0.5)
        left = running_vivo()
        if not left:
            return True, 'Vivo PC Suite closed'
    return False, ('Still running: %s. Please close Vivo manually '
                   '(system tray > Exit) and try again.' % ', '.join(left))


def start_vivo(root):
    """Relaunch the suite after patching. Returns message."""
    import subprocess
    exe = os.path.join(root, 'pcsuite.exe')
    if not os.path.exists(exe):
        return 'pcsuite.exe not found, not relaunched'
    try:
        subprocess.Popen([exe], cwd=root, close_fds=True)
    except OSError as e:
        return 'could not relaunch (%s) — please start it manually' % e
    return 'Vivo PC Suite restarted'


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Vivo PC Suite English Patcher')
        self.resizable(False, False)
        self.rootv = tk.StringVar()
        self.asarv = tk.StringVar()
        self.status = tk.StringVar(value='Searching for an installation...')
        # Theme follows the user's system. No question asked.
        self.dark = system_is_dark()
        self.colors = apply_theme(self, self.dark)
        self.theme_caption = tk.StringVar()
        r = 0
        head = ttk.Frame(self)
        head.grid(row=r, column=0, padx=10, pady=(10, 0), sticky='ew')
        self.logo = tk.Canvas(head, width=46, height=46, highlightthickness=0)
        self.logo.pack(side='left')
        titlebox = ttk.Frame(head)
        titlebox.pack(side='left', padx=(8, 0))
        ttk.Label(titlebox, text='Vivo PC Suite English Patcher',
                  style='Title.TLabel').pack(anchor='w')
        ttk.Label(titlebox, text='Phone Mirroring  •  Main App  •  Settings',
                  style='Sub.TLabel').pack(anchor='w')
        self.theme_btn = ttk.Button(head, command=self.toggle_theme)
        self.theme_btn.pack(side='right')
        ttk.Label(self, textvariable=self.theme_caption,
                  style='Sub.TLabel').grid(row=r + 1, column=0, sticky='e', padx=10)
        self.paint_logo()
        self.sync_theme_ui()
        ttk.Label(self, text='Vivo installation folder (pcsuite):').grid(row=r + 2, column=0, sticky='w', padx=10, pady=(6, 0))
        f1 = ttk.Frame(self)
        f1.grid(row=r + 3, column=0, padx=10, sticky='ew')
        ttk.Entry(f1, textvariable=self.rootv, width=60).pack(side='left', expand=True, fill='x')
        ttk.Button(f1, text='Browse...', command=self.browse_root).pack(side='left', padx=(5, 0))
        ttk.Label(self, text='Translated English app.asar (provided alongside this tool):').grid(row=r + 4, column=0, sticky='w', padx=10, pady=(8, 0))
        f2 = ttk.Frame(self)
        f2.grid(row=r + 5, column=0, padx=10, sticky='ew')
        ttk.Entry(f2, textvariable=self.asarv, width=60).pack(side='left', expand=True, fill='x')
        ttk.Button(f2, text='Browse...', command=self.browse_asar).pack(side='left', padx=(5, 0))
        ttk.Label(self, textvariable=self.status, wraplength=480).grid(row=r + 6, column=0, sticky='w', padx=10, pady=5)
        btns = ttk.Frame(self)
        btns.grid(row=r + 7, column=0, pady=(0, 5))
        ttk.Button(btns, text='Apply English Patch', command=self.do_all).pack(side='left', padx=5)
        ttk.Button(btns, text='Restore Backups', command=self.do_restore).pack(side='left', padx=5)
        ttk.Button(btns, text='Quit', command=self.destroy).pack(side='left', padx=5)
        self.log = tk.Text(self, height=9, width=70, state='disabled')
        self.log.grid(row=r + 8, column=0, padx=10, pady=(0, 10))
        self.style_log()
        self.auto_find()

    def paint_logo(self):
        """Blue rounded badge with a white V + wordmark. No image file needed."""
        c = self.colors
        self.logo.configure(bg=c['bg'])
        self.logo.delete('all')
        self.logo.create_oval(3, 3, 43, 43, fill=VIVO_BLUE, outline=VIVO_BLUE)
        self.logo.create_text(23, 24, text='V', fill=c['logo_fg'],
                              font=('Segoe UI', 22, 'bold'))

    def sync_theme_ui(self):
        self.theme_btn.configure(
            text='Switch to Light Mode' if self.dark else 'Switch to Dark Mode')
        self.theme_caption.set(
            'Theme: %s (following your system)' % ('Dark' if self.dark else 'Light')
            if getattr(self, 'follow_system', True) else
            'Theme: %s (manual)' % ('Dark' if self.dark else 'Light'))

    def toggle_theme(self):
        self.follow_system = False
        self.dark = not self.dark
        self.colors = apply_theme(self, self.dark)
        self.paint_logo()
        self.style_log()
        self.sync_theme_ui()
        self.say('Theme: %s mode' % ('dark' if self.dark else 'light'))

    def style_log(self):
        c = self.colors
        self.log.configure(bg=c['logbg'], fg=c['logfg'],
                           insertbackground=c['logfg'])

    def say(self, msg):
        self.log.configure(state='normal')
        self.log.insert('end', msg + '\n')
        self.log.configure(state='disabled')
        self.log.see('end')

    def paths(self):
        root = self.rootv.get().strip()
        exe = os.path.join(root, 'vivoScreen', 'vivoScreen.exe')
        asar = os.path.join(root, 'resources', 'app.asar')
        return exe, asar

    def auto_find(self):
        # 1. Ask Windows where Vivo actually runs from (MuiCache records).
        for c in find_via_windows():
            self.rootv.set(c)
            self.say('Detected via Windows records: ' + c)
            break
        # 2. Fall back to well-known install folders.
        if not self.rootv.get():
            for c in ROOT_CANDIDATES:
                if os.path.exists(os.path.join(c, 'vivoScreen', 'vivoScreen.exe')):
                    self.rootv.set(c)
                    self.say('Detected via standard folders: ' + c)
                    break
        for c in ASAR_CANDIDATES:
            if os.path.exists(c):
                self.asarv.set(c)
                break
        self.refresh()
        if not self.rootv.get():
            self.say('No installation found — please use Browse')

    def browse_root(self):
        p = filedialog.askdirectory(title='Select the Vivo installation folder (pcsuite)')
        if p:
            self.rootv.set(p)
            self.refresh()

    def browse_asar(self):
        p = filedialog.askopenfilename(title='Select the translated English app.asar',
                                       filetypes=[('asar', '*.asar')])
        if p:
            self.asarv.set(p)
            self.refresh()

    def refresh(self):
        exe, asar = self.paths()
        info = []
        if os.path.exists(exe):
            d, detail = describe_exe(exe)
            info.append(detail)
        else:
            info.append('%s: executable not found in this folder' % MIRROR_NAME)
        info.append('Main app archive (app.asar): ' + ('present' if os.path.exists(asar) else 'missing'))
        info.append('English source archive: ' + ('ready' if os.path.exists(self.asarv.get().strip()) else 'please select a file'))
        self.status.set(' | '.join(info))

    def do_all(self):
        exe, asar = self.paths()
        src = self.asarv.get().strip()
        if not os.path.exists(exe):
            messagebox.showerror('Error', '%s was not found in this folder.\nPlease check the installation path.' % MIRROR_NAME)
            return
        if not os.path.exists(src):
            messagebox.showerror('Error', 'Please select the translated English app.asar first.')
            return
        if not messagebox.askokcancel('Confirm',
                                      'Apply the English patch?\n'
                                      'Vivo will be closed first, then restarted.\n'
                                      '(%s + language settings + main app archive — backups are kept)' % MIRROR_NAME):
            return
        try:
            ok, msg = close_vivo(self.say)
            self.say(msg)
            if not ok:
                messagebox.showerror('Error', msg)
                return
            state = detect_exe(exe)
            if state == 'en':
                self.say('%s is already English, continuing (settings + app archive)' % MIRROR_NAME)
            elif state == 'zh':
                ok, msg = patch_exe(exe)
                self.say(msg)
                if not ok:
                    messagebox.showerror('Error', msg)
                    return
            else:
                _, detail = describe_exe(exe)
                msg = detail + ' — stopped. Please check the installation folder.'
                self.say(msg)
                messagebox.showerror('Error', msg)
                return
            ok, msg = patch_config()
            self.say(msg)
            ok, msg = install_asar(src, asar)
            self.say(msg)
            if not ok:
                messagebox.showerror('Error', msg)
                return
        except OSError as e:
            messagebox.showerror('Error',
                                 'Write access denied. Please relaunch as administrator.\n%s' % e)
            return
        self.say(start_vivo(self.rootv.get().strip()))
        self.refresh()
        messagebox.showinfo('Done', 'English patch applied.\nVivo PC Suite was restarted.')

    def do_restore(self):
        exe, asar = self.paths()
        names = []
        if os.path.exists(exe + '.old'):
            names.append(MIRROR_NAME)
        if os.path.exists(asar + '.old'):
            names.append('main app archive')
        if not names:
            messagebox.showinfo('Info', 'No backups found, nothing to restore.')
            return
        if not messagebox.askokcancel('Confirm',
                                      'Restore from backups: %s?\nVivo will be closed first, then restarted.' % ' + '.join(names)):
            return
        try:
            ok, msg = close_vivo(self.say)
            self.say(msg)
            if not ok:
                messagebox.showerror('Error', msg)
                return
            if os.path.exists(exe + '.old'):
                shutil.copy2(exe + '.old', exe)
                self.say('%s restored from backup' % MIRROR_NAME)
            if os.path.exists(asar + '.old'):
                shutil.copy2(asar + '.old', asar)
                self.say('Main app archive restored from backup')
        except OSError as e:
            messagebox.showerror('Error',
                                 'Write access denied. Please relaunch as administrator.\n%s' % e)
            return
        self.say(start_vivo(self.rootv.get().strip()))
        self.refresh()


if __name__ == '__main__':
    App().mainloop()

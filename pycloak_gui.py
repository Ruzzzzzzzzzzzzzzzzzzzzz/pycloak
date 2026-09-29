#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

BUILD_CMD = [sys.executable, '-X', 'utf8', '-m', 'pycloak.cli']

STRINGS = {
    'zh': {
        'title': 'PyCloak 混淆器控制台',
        'lang_btn': 'EN',
        'tab_build': ' 构建 ',
        'tab_lic': ' License ',
        'tab_nat': ' 原生强化 ',
        'log': '日志',
        'ready': '[PyCloak] 就绪。项目根: %s',
        'project': '项目',
        'entry': '入口脚本',
        'output': '输出文件',
        'output_hint': '（留空 = <入口>_protected.py）',
        'browse': '浏览...',
        'obf_opts': '混淆选项',
        'vm_mods': 'VM 保护模块',
        'vm_hint': '（逗号分隔；mod 整模块 / mod:func 单函数）',
        'flatten': '控制流扁平化',
        'rename': '重命名参数',
        'antidbg': '反调试',
        'timing': '计时检测',
        'pyz': 'zipapp (.pyz)',
        'deadcode': '死代码强度',
        'seed': '随机种子（可选）',
        'banner': '头部注释',
        'lic_bind': 'License 绑定',
        'lic_author': '作者密钥（每次构建自动生成密钥对并内嵌 license，私钥存 <输出>.author.key）',
        'lic_pub': '公钥绑定',
        'lic_embed': '内嵌 license',
        'lic_off': '不启用',
        'build_btn': '开始构建',
        'run_btn': '运行产物',
        'keygen': '密钥生成',
        'key_dir': '输出目录',
        'key_bits': '位数',
        'keygen_btn': '生成密钥对',
        'fp_sign': '指纹与签发',
        'priv_key': '私钥',
        'fp': '指纹',
        'fp_read': '读取本机',
        'fp_copy': '复制',
        'expire': '过期',
        'expire_hint': '（YYYY-MM-DD，留空不过期；指纹填 * 表示任意机器）',
        'lic_out': '输出',
        'sign_btn': '签发 license',
        'verify_btn': '本地验证',
        'payload': '已保护产物',
        'nat_out': '输出（可选）',
        'cython_btn': 'Cython 编译 (.pyd)',
        'nuitka_btn': 'Nuitka 单文件 (.exe)',
        'nat_hint': '需要本机装有 cython / nuitka 与 C 编译器；编译后 license.key 放 exe 同目录（或构建时内嵌）。',
        'log_build': '[构建] %s',
        'log_done': '[完成] 退出码 %s',
        'log_built': '[构建] 产物: %s',
        'log_run': '[运行] %s',
        'log_run_end': '[运行结束] 退出码 %s',
        'log_keygen': '[keygen] %s bits -> %s',
        'log_fp': '[fingerprint] 读取本机指纹...',
        'log_fp_got': '[fingerprint] %s',
        'log_fp_ok': '[fingerprint] 完成',
        'log_copy': '[复制] 指纹已复制到剪贴板',
        'log_sign': '[sign] %s',
        'log_verify': '[verify] %s <- %s',
        'log_cython': '[cython] %s',
        'log_nuitka': '[nuitka] %s',
        'log_err': '[错误] %s',
        'warn_busy': '已有任务在运行，请等待完成。',
        'warn_entry': '请选择入口脚本。',
        'warn_pub': '选择公钥文件，或改用「作者密钥」模式。',
        'warn_key': '选择私钥文件。',
        'warn_vf': '选择公钥与 license 文件。',
        'warn_payload': '选择已保护的产物（或先构建）。',
        'warn_run': '先构建成功再运行。',
        'sel_py': '选择入口脚本',
        'sel_pem': '选择密钥文件',
        'sel_lic': '选择 license 文件',
        'sel_file': '选择文件',
        'sel_dir': '选择目录',
        'ft_py': 'Python 文件',
        'ft_pem': 'PEM 文件',
        'ft_lic': 'License',
        'ft_all': '全部',
        'tip': '提示',
    },
    'en': {
        'title': 'PyCloak Obfuscator Console',
        'lang_btn': '中文',
        'tab_build': ' Build ',
        'tab_lic': ' License ',
        'tab_nat': ' Native ',
        'log': 'Log',
        'ready': '[PyCloak] Ready. Project root: %s',
        'project': 'Project',
        'entry': 'Entry script',
        'output': 'Output file',
        'output_hint': '(blank = <entry>_protected.py)',
        'browse': 'Browse...',
        'obf_opts': 'Obfuscation options',
        'vm_mods': 'VM-protected modules',
        'vm_hint': '(comma separated; mod = whole module / mod:func = one function)',
        'flatten': 'Control-flow flattening',
        'rename': 'Rename parameters',
        'antidbg': 'Anti-debug',
        'timing': 'Timing check',
        'pyz': 'zipapp (.pyz)',
        'deadcode': 'Dead-code intensity',
        'seed': 'Random seed (optional)',
        'banner': 'Header comment',
        'lic_bind': 'License binding',
        'lic_author': 'Author key (auto keypair per build, embedded license, private key at <output>.author.key)',
        'lic_pub': 'Public key binding',
        'lic_embed': 'Embed license',
        'lic_off': 'Disabled',
        'build_btn': 'Build',
        'run_btn': 'Run output',
        'keygen': 'Key generation',
        'key_dir': 'Output directory',
        'key_bits': 'Bits',
        'keygen_btn': 'Generate keypair',
        'fp_sign': 'Fingerprint & signing',
        'priv_key': 'Private key',
        'fp': 'Fingerprint',
        'fp_read': 'Read this machine',
        'fp_copy': 'Copy',
        'expire': 'Expire',
        'expire_hint': '(YYYY-MM-DD, blank = never; fingerprint * = any machine)',
        'lic_out': 'Output',
        'sign_btn': 'Sign license',
        'verify_btn': 'Verify locally',
        'payload': 'Protected payload',
        'nat_out': 'Output (optional)',
        'cython_btn': 'Cython compile (.pyd)',
        'nuitka_btn': 'Nuitka onefile (.exe)',
        'nat_hint': 'Requires cython / nuitka and a C compiler. Ship license.key next to the exe (or embed at build time).',
        'log_build': '[build] %s',
        'log_done': '[done] exit code %s',
        'log_built': '[build] output: %s',
        'log_run': '[run] %s',
        'log_run_end': '[run finished] exit code %s',
        'log_keygen': '[keygen] %s bits -> %s',
        'log_fp': '[fingerprint] reading this machine...',
        'log_fp_got': '[fingerprint] %s',
        'log_fp_ok': '[fingerprint] done',
        'log_copy': '[copy] fingerprint copied to clipboard',
        'log_sign': '[sign] %s',
        'log_verify': '[verify] %s <- %s',
        'log_cython': '[cython] %s',
        'log_nuitka': '[nuitka] %s',
        'log_err': '[error] %s',
        'warn_busy': 'A task is already running. Please wait.',
        'warn_entry': 'Select an entry script first.',
        'warn_pub': 'Select a public key, or use "Author key" mode.',
        'warn_key': 'Select a private key first.',
        'warn_vf': 'Select both a public key and a license file.',
        'warn_payload': 'Select a protected payload (or build first).',
        'warn_run': 'Build successfully before running.',
        'sel_py': 'Select entry script',
        'sel_pem': 'Select key file',
        'sel_lic': 'Select license file',
        'sel_file': 'Select file',
        'sel_dir': 'Select directory',
        'ft_py': 'Python files',
        'ft_pem': 'PEM files',
        'ft_lic': 'License',
        'ft_all': 'All files',
        'tip': 'Notice',
    },
}


class Worker(threading.Thread):
    def __init__(self, args, cwd, on_line, on_done):
        super().__init__(daemon=True)
        self.args = args
        self.cwd = cwd
        self.on_line = on_line
        self.on_done = on_done
        self.proc = None

    def run(self):
        try:
            self.proc = subprocess.Popen(
                BUILD_CMD + self.args, cwd=self.cwd,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding='utf-8', errors='replace',
                bufsize=1, creationflags=subprocess.CREATE_NO_WINDOW)
            for line in self.proc.stdout:
                self.on_line(line.rstrip())
            self.proc.wait()
            self.on_done(self.proc.returncode)
        except Exception as e:
            self.on_line('[error] %s' % e)
            self.on_done(1)

    def kill(self):
        if self.proc and self.proc.poll() is None:
            self.proc.kill()


class App(tk.Tk):
    def __init__(self, lang=None):
        super().__init__()
        self.lang = lang or ('en' if self._system_english() else 'zh')
        self.T = STRINGS[self.lang]
        self.worker = None
        self.last_out = None
        self.last_pyz = None
        self._i18n = []
        self._build_ui()
        self.set_lang(self.lang)

    @staticmethod
    def _system_english():
        try:
            import locale
            return (locale.getlocale()[0] or '').startswith('en')
        except Exception:
            return False

    def t(self, key, *args):
        s = self.T.get(key, key)
        return s % args if args else s

    def set_lang(self, lang):
        self.lang = lang
        self.T = STRINGS[lang]
        self.title(self.t('title'))
        for widget, key in self._i18n:
            try:
                widget.configure(text=self.t(key))
            except tk.TclError:
                pass
        self.nb.tab(0, text=self.t('tab_build'))
        self.nb.tab(1, text=self.t('tab_lic'))
        self.nb.tab(2, text=self.t('tab_nat'))
        self.logf.configure(text=self.t('log'))
        self.btn_lang.configure(text=self.t('lang_btn'))

    def toggle_lang(self):
        self.set_lang('en' if self.lang == 'zh' else 'zh')

    def _reg(self, widget, key):
        self._i18n.append((widget, key))
        return widget

    def log(self, line):
        ts = time.strftime('%H:%M:%S')
        self.txt.configure(state='normal')
        self.txt.insert('end', '[%s] %s\n' % (ts, line))
        self.txt.see('end')
        self.txt.configure(state='disabled')

    def _pick(self, var, kind):
        if kind == 'py':
            p = filedialog.askopenfilename(
                title=self.t('sel_py'),
                filetypes=[(self.t('ft_py'), '*.py'), (self.t('ft_all'), '*.*')])
        elif kind == 'pem':
            p = filedialog.askopenfilename(
                title=self.t('sel_pem'),
                filetypes=[(self.t('ft_pem'), '*.pem *.pub'), (self.t('ft_all'), '*.*')])
        elif kind == 'lic':
            p = filedialog.askopenfilename(
                title=self.t('sel_lic'),
                filetypes=[(self.t('ft_lic'), '*.key *.lic'), (self.t('ft_all'), '*.*')])
        else:
            p = filedialog.askopenfilename(title=self.t('sel_file'))
        if p:
            var.set(p)

    def _pick_dir(self, var):
        p = filedialog.askdirectory(title=self.t('sel_dir'))
        if p:
            var.set(p)

    def _run(self, args, done=None):
        if self.worker and self.worker.is_alive():
            messagebox.showwarning(self.t('tip'), self.t('warn_busy'))
            return False
        self.btn_build.configure(state='disabled')
        self.btn_run.configure(state='disabled')

        def on_line(line):
            self.after(0, lambda l=line: self.log(l))

        def on_done(code):
            self.after(0, lambda: self._finish(code, done))

        self.worker = Worker(args, ROOT, on_line, on_done)
        self.worker.start()
        return True

    def _run_direct(self, cmd, done):
        if self.worker and self.worker.is_alive():
            messagebox.showwarning(self.t('tip'), self.t('warn_busy'))
            return
        self.btn_build.configure(state='disabled')
        self.btn_run.configure(state='disabled')

        def on_line(line):
            self.after(0, lambda l=line: self.log(l))

        def on_done(code):
            self.after(0, lambda: self._finish(code, done))

        class _W(threading.Thread):
            def run(self):
                try:
                    self.p = subprocess.Popen(
                        cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, encoding='utf-8', errors='replace', bufsize=1,
                        creationflags=subprocess.CREATE_NO_WINDOW)
                    for line in self.p.stdout:
                        on_line(line.rstrip())
                    self.p.wait()
                    on_done(self.p.returncode)
                except Exception as e:
                    on_line('[error] %s' % e)
                    on_done(1)

        self.worker = _W(daemon=True)
        self.worker.start()

    def _finish(self, code, done):
        self.btn_build.configure(state='normal')
        self.log(self.t('log_done', code))
        if done:
            done(code)

    def _build_args(self):
        entry = self.v_entry.get().strip()
        if not entry:
            messagebox.showwarning(self.t('tip'), self.t('warn_entry'))
            return None
        args = ['build', entry]
        out = self.v_out.get().strip()
        if out:
            args += ['-o', out]
        for vm in [x.strip() for x in self.v_vm.get().split(',') if x.strip()]:
            args += ['--vm', vm]
        if self.v_flatten.get():
            args.append('--flatten')
        if self.v_rename.get():
            args.append('--rename-params')
        if self.v_antidbg.get():
            args.append('--anti-debug')
        if self.v_timing.get():
            args.append('--timing')
        if self.v_pyz.get():
            args.append('--pyz')
        try:
            dc = int(self.v_dead.get())
            if dc != 2:
                args += ['--dead-code', str(dc)]
        except ValueError:
            pass
        seed = self.v_seed.get().strip()
        if seed:
            args += ['--seed', seed]
        banner = self.v_banner.get().strip()
        if banner:
            args += ['--banner', banner]
        mode = self.v_licmode.get()
        if mode == 'off':
            args.append('--no-license')
        elif mode == 'pub':
            pub = self.v_pub.get().strip()
            if not pub:
                messagebox.showwarning(self.t('tip'), self.t('warn_pub'))
                return None
            args += ['--pubkey', pub]
            lic = self.v_lic.get().strip()
            if lic:
                args += ['--license', lic]
        return args

    def on_build(self):
        args = self._build_args()
        if args is None:
            return
        self.log(self.t('log_build', ' '.join(args)))
        entry = self.v_entry.get().strip()
        out = self.v_out.get().strip() or os.path.splitext(entry)[0] + '_protected.py'
        self.last_out = os.path.normpath(os.path.join(ROOT, out))
        self.last_pyz = os.path.splitext(self.last_out)[0] + '.pyz' if self.v_pyz.get() else None

        def done(code):
            if code == 0:
                self.btn_run.configure(state='normal')
                self.log(self.t('log_built', self.last_out))

        self._run(args, done)

    def on_run(self):
        if not self.last_out or not os.path.exists(self.last_out):
            messagebox.showwarning(self.t('tip'), self.t('warn_run'))
            return
        self.log(self.t('log_run', self.last_out))
        self._run_direct([sys.executable, '-X', 'utf8', self.last_out],
                         lambda code: self.log(self.t('log_run_end', code)))

    def on_keygen(self):
        out = self.v_keydir.get().strip() or 'keys'
        bits = self.v_bits.get()
        self.log(self.t('log_keygen', bits, out))
        self._run(['keygen', '-o', out, '-b', bits])

    def on_fingerprint(self):
        self.log(self.t('log_fp'))
        try:
            r = subprocess.run(
                BUILD_CMD + ['fingerprint'], cwd=ROOT,
                capture_output=True, text=True, encoding='utf-8',
                creationflags=subprocess.CREATE_NO_WINDOW)
            fp = r.stdout.strip()
            self.v_fp.set(fp)
            self.log(self.t('log_fp_got', fp))
        except Exception as e:
            self.log(self.t('log_err', e))

    def on_copy_fp(self):
        fp = self.v_fp.get().strip()
        if not fp:
            return
        self.clipboard_clear()
        self.clipboard_append(fp)
        self.log(self.t('log_copy'))

    def on_sign(self):
        key = self.v_key.get().strip()
        if not key:
            messagebox.showwarning(self.t('tip'), self.t('warn_key'))
            return
        args = ['sign', '-k', key]
        fp = self.v_fp.get().strip()
        if fp:
            args += ['-f', fp]
        exp = self.v_exp.get().strip()
        if exp:
            args += ['-e', exp]
        out = self.v_licout.get().strip()
        if out:
            args += ['-o', out]
        self.log(self.t('log_sign', ' '.join(args)))
        self._run(args)

    def on_verify(self):
        pub = self.v_pub.get().strip()
        lic = self.v_lic.get().strip()
        if not pub or not lic:
            messagebox.showwarning(self.t('tip'), self.t('warn_vf'))
            return
        self.log(self.t('log_verify', lic, pub))
        self._run(['verify', '-p', pub, lic])

    def _payload(self):
        p = self.v_payload.get().strip() or (self.last_out or '')
        if not p or not os.path.exists(p):
            messagebox.showwarning(self.t('tip'), self.t('warn_payload'))
            return None
        return p

    def on_cython(self):
        payload = self._payload()
        if not payload:
            return
        out = self.v_natout.get().strip() or ''
        args = [os.path.join(ROOT, 'build_cython.py'), payload]
        if out:
            args += ['-o', out]
        self.log(self.t('log_cython', ' '.join(args)))
        self._run_direct([sys.executable, '-X', 'utf8'] + args, lambda c: None)

    def on_nuitka(self):
        payload = self._payload()
        if not payload:
            return
        out = self.v_natout.get().strip() or ''
        args = [os.path.join(ROOT, 'build_nuitka.py'), payload]
        if out:
            args += ['-o', out]
        self.log(self.t('log_nuitka', ' '.join(args)))
        self._run_direct([sys.executable, '-X', 'utf8'] + args, lambda c: None)

    def _build_ui(self):
        pad = {'padx': 6, 'pady': 3}
        top = ttk.Frame(self)
        top.pack(fill='x', padx=8, pady=(6, 0))
        self.btn_lang = ttk.Button(top, text='', width=8, command=self.toggle_lang)
        self.btn_lang.pack(side='right')

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill='both', expand=True, padx=8, pady=6)

        f_build = ttk.Frame(self.nb, padding=8)
        self.nb.add(f_build, text='')

        box = ttk.LabelFrame(f_build, padding=8)
        box.pack(fill='x', **pad)
        self._reg(box, 'project')
        self.v_entry = tk.StringVar()
        self.v_out = tk.StringVar()
        r = 0
        self._reg(ttk.Label(box), 'entry').grid(row=r, column=0, sticky='w')
        ttk.Entry(box, textvariable=self.v_entry, width=60).grid(row=r, column=1, sticky='we', padx=4)
        ttk.Button(box, text='...', width=6, command=lambda: self._pick(self.v_entry, 'py')).grid(row=r, column=2)
        r += 1
        self._reg(ttk.Label(box), 'output').grid(row=r, column=0, sticky='w')
        ttk.Entry(box, textvariable=self.v_out, width=60).grid(row=r, column=1, sticky='we', padx=4)
        self._reg(ttk.Label(box), 'output_hint').grid(row=r, column=2, sticky='w')
        box.columnconfigure(1, weight=1)

        box2 = ttk.LabelFrame(f_build, padding=8)
        box2.pack(fill='x', **pad)
        self._reg(box2, 'obf_opts')
        self.v_vm = tk.StringVar(value='payment_core')
        self.v_flatten = tk.BooleanVar(value=True)
        self.v_rename = tk.BooleanVar(value=True)
        self.v_antidbg = tk.BooleanVar(value=True)
        self.v_timing = tk.BooleanVar(value=False)
        self.v_pyz = tk.BooleanVar(value=False)
        self.v_dead = tk.StringVar(value='2')
        self.v_seed = tk.StringVar()
        self.v_banner = tk.StringVar()
        self._reg(ttk.Label(box2), 'vm_mods').grid(row=0, column=0, sticky='w')
        ttk.Entry(box2, textvariable=self.v_vm, width=44).grid(row=0, column=1, columnspan=2, sticky='we', padx=4)
        self._reg(ttk.Label(box2), 'vm_hint').grid(row=0, column=3, sticky='w')
        self._reg(ttk.Checkbutton(box2, variable=self.v_flatten), 'flatten').grid(row=1, column=0, sticky='w')
        self._reg(ttk.Checkbutton(box2, variable=self.v_rename), 'rename').grid(row=1, column=1, sticky='w')
        self._reg(ttk.Checkbutton(box2, variable=self.v_antidbg), 'antidbg').grid(row=1, column=2, sticky='w')
        self._reg(ttk.Checkbutton(box2, variable=self.v_timing), 'timing').grid(row=1, column=3, sticky='w')
        self._reg(ttk.Checkbutton(box2, variable=self.v_pyz), 'pyz').grid(row=2, column=0, sticky='w')
        self._reg(ttk.Label(box2), 'deadcode').grid(row=2, column=1, sticky='w')
        ttk.Spinbox(box2, from_=0, to=10, textvariable=self.v_dead, width=5).grid(row=2, column=2, sticky='w')
        self._reg(ttk.Label(box2), 'seed').grid(row=3, column=0, sticky='w')
        ttk.Entry(box2, textvariable=self.v_seed, width=16).grid(row=3, column=1, sticky='w')
        self._reg(ttk.Label(box2), 'banner').grid(row=3, column=2, sticky='w')
        ttk.Entry(box2, textvariable=self.v_banner, width=28).grid(row=3, column=3, sticky='w')

        box3 = ttk.LabelFrame(f_build, padding=8)
        box3.pack(fill='x', **pad)
        self._reg(box3, 'lic_bind')
        self.v_licmode = tk.StringVar(value='author')
        self.v_pub = tk.StringVar()
        self.v_lic = tk.StringVar()
        self._reg(ttk.Radiobutton(box3, variable=self.v_licmode, value='author'), 'lic_author'
                  ).grid(row=0, column=0, columnspan=4, sticky='w')
        self._reg(ttk.Radiobutton(box3, variable=self.v_licmode, value='pub'), 'lic_pub').grid(row=1, column=0, sticky='w')
        ttk.Entry(box3, textvariable=self.v_pub, width=52).grid(row=1, column=1, columnspan=2, sticky='we', padx=4)
        self._reg(ttk.Button(box3, command=lambda: self._pick(self.v_pub, 'pem')), 'browse').grid(row=1, column=3)
        self._reg(ttk.Label(box3), 'lic_embed').grid(row=2, column=0, sticky='w')
        ttk.Entry(box3, textvariable=self.v_lic, width=52).grid(row=2, column=1, columnspan=2, sticky='we', padx=4)
        self._reg(ttk.Button(box3, command=lambda: self._pick(self.v_lic, 'lic')), 'browse').grid(row=2, column=3)
        self._reg(ttk.Radiobutton(box3, variable=self.v_licmode, value='off'), 'lic_off').grid(row=3, column=0, sticky='w')
        box3.columnconfigure(1, weight=1)

        btns = ttk.Frame(f_build)
        btns.pack(fill='x', pady=8)
        self.btn_build = self._reg(ttk.Button(btns, command=self.on_build), 'build_btn')
        self.btn_build.pack(side='left', padx=4)
        self.btn_run = self._reg(ttk.Button(btns, command=self.on_run, state='disabled'), 'run_btn')
        self.btn_run.pack(side='left', padx=4)

        f_lic = ttk.Frame(self.nb, padding=8)
        self.nb.add(f_lic, text='')

        b1 = ttk.LabelFrame(f_lic, padding=8)
        b1.pack(fill='x', **pad)
        self._reg(b1, 'keygen')
        self.v_keydir = tk.StringVar(value='keys')
        self.v_bits = tk.StringVar(value='2048')
        self._reg(ttk.Label(b1), 'key_dir').grid(row=0, column=0, sticky='w')
        ttk.Entry(b1, textvariable=self.v_keydir, width=44).grid(row=0, column=1, sticky='we', padx=4)
        self._reg(ttk.Button(b1, command=lambda: self._pick_dir(self.v_keydir)), 'browse').grid(row=0, column=2)
        self._reg(ttk.Label(b1), 'key_bits').grid(row=0, column=3, sticky='w', padx=(12, 0))
        ttk.Combobox(b1, textvariable=self.v_bits, values=('1024', '2048', '4096'), width=6).grid(row=0, column=4)
        self._reg(ttk.Button(b1, command=self.on_keygen), 'keygen_btn').grid(row=0, column=5, padx=8)

        b2 = ttk.LabelFrame(f_lic, padding=8)
        b2.pack(fill='x', **pad)
        self._reg(b2, 'fp_sign')
        self.v_key = tk.StringVar(value='keys/key.pem')
        self.v_fp = tk.StringVar()
        self.v_exp = tk.StringVar()
        self.v_licout = tk.StringVar(value='license.key')
        self._reg(ttk.Label(b2), 'priv_key').grid(row=0, column=0, sticky='w')
        ttk.Entry(b2, textvariable=self.v_key, width=48).grid(row=0, column=1, columnspan=2, sticky='we', padx=4)
        self._reg(ttk.Button(b2, command=lambda: self._pick(self.v_key, 'pem')), 'browse').grid(row=0, column=3)
        self._reg(ttk.Label(b2), 'fp').grid(row=1, column=0, sticky='w')
        ttk.Entry(b2, textvariable=self.v_fp, width=48).grid(row=1, column=1, columnspan=2, sticky='we', padx=4)
        self._reg(ttk.Button(b2, command=self.on_fingerprint), 'fp_read').grid(row=1, column=3)
        self._reg(ttk.Button(b2, command=self.on_copy_fp), 'fp_copy').grid(row=1, column=4, padx=4)
        self._reg(ttk.Label(b2), 'expire').grid(row=2, column=0, sticky='w')
        ttk.Entry(b2, textvariable=self.v_exp, width=14).grid(row=2, column=1, sticky='w')
        self._reg(ttk.Label(b2), 'expire_hint').grid(row=2, column=2, columnspan=2, sticky='w')
        self._reg(ttk.Label(b2), 'lic_out').grid(row=3, column=0, sticky='w')
        ttk.Entry(b2, textvariable=self.v_licout, width=48).grid(row=3, column=1, columnspan=2, sticky='we', padx=4)
        self._reg(ttk.Button(b2, command=self.on_sign), 'sign_btn').grid(row=3, column=3)
        self._reg(ttk.Button(b2, command=self.on_verify), 'verify_btn').grid(row=3, column=4, padx=4)

        f_nat = ttk.Frame(self.nb, padding=8)
        self.nb.add(f_nat, text='')
        b3 = ttk.LabelFrame(f_nat, padding=8)
        b3.pack(fill='x', **pad)
        self._reg(b3, 'tab_nat')
        self.v_payload = tk.StringVar()
        self.v_natout = tk.StringVar()
        self._reg(ttk.Label(b3), 'payload').grid(row=0, column=0, sticky='w')
        ttk.Entry(b3, textvariable=self.v_payload, width=56).grid(row=0, column=1, columnspan=2, sticky='we', padx=4)
        self._reg(ttk.Button(b3, command=lambda: self._pick(self.v_payload, 'py')), 'browse').grid(row=0, column=3)
        self._reg(ttk.Label(b3), 'nat_out').grid(row=1, column=0, sticky='w')
        ttk.Entry(b3, textvariable=self.v_natout, width=56).grid(row=1, column=1, columnspan=2, sticky='we', padx=4)
        self._reg(ttk.Button(b3, command=self.on_cython), 'cython_btn').grid(row=2, column=1, sticky='w', pady=6)
        self._reg(ttk.Button(b3, command=self.on_nuitka), 'nuitka_btn').grid(row=2, column=2, sticky='w', pady=6)
        self._reg(ttk.Label(b3, foreground='#666'), 'nat_hint').grid(
            row=3, column=0, columnspan=4, sticky='w')

        self.logf = ttk.LabelFrame(self, padding=4)
        self.logf.pack(fill='both', expand=True, padx=8, pady=(0, 6))
        self.txt = scrolledtext.ScrolledText(self.logf, height=10, state='disabled',
                                             font=('Consolas', 9), bg='#141414', fg='#c8c8c8')
        self.txt.pack(fill='both', expand=True)


def main():
    if '--selftest' in sys.argv:
        app = App()
        app.after(600, app.toggle_lang)
        app.after(1200, app.destroy)
        app.mainloop()
        print('GUI OK (lang switch exercised)')
        return 0
    App().mainloop()
    return 0


if __name__ == '__main__':
    sys.exit(main())

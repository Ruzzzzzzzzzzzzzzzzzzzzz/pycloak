#!/usr/bin/env python3

import argparse
import os
import shutil
import subprocess
import sys


def main():
    ap = argparse.ArgumentParser(description='Cython-harden a PyCloak payload')
    ap.add_argument('payload', help='protected .py produced by `pycloak build`')
    ap.add_argument('-o', '--out', default=None, help='output directory')
    ap.add_argument('--keep-c', action='store_true', help='keep the generated C file')
    args = ap.parse_args()

    try:
        from setuptools import setup
        from setuptools.extension import Extension
        from Cython.Build import cythonize
    except ImportError as e:
        print('[!] missing build deps: %s' % e)
        print('    install with: pip install cython setuptools')
        return 1

    out_dir = args.out or os.path.join(os.path.dirname(os.path.abspath(args.payload)), 'native')
    os.makedirs(out_dir, exist_ok=True)
    work = os.path.join(out_dir, '_build')
    os.makedirs(work, exist_ok=True)

    payload_abs = os.path.abspath(args.payload)
    mod_name = '_core'
    c_path = os.path.join(work, mod_name + '.py')
    shutil.copyfile(payload_abs, c_path)

    launcher = os.path.join(out_dir, 'launcher.py')
    with open(launcher, 'w', encoding='utf-8') as f:
        f.write('import _core\n\n\nif __name__ == "__main__":\n    pass\n')

    sys.argv = [sys.argv[0], 'build_ext', '--build-lib', out_dir, '--build-temp', work]
    ext = Extension(
        mod_name,
        sources=[c_path],
        extra_compile_args=['/O2', '/GL'] if os.name == 'nt' else ['-O3'],
    )
    try:
        setup(
            name='pycloak_core',
            script_args=['build_ext', '--build-lib', out_dir, '--build-temp', work],
            ext_modules=cythonize(
                [ext],
                compiler_directives={'language_level': '3'},
                quiet=False),
        )
    except SystemExit as e:
        if e.code not in (0, None):
            print('[!] build_ext failed (%s)' % e.code)
            return e.code or 1

    if not args.keep_c:
        for f in os.listdir(work):
            if f.endswith('.c'):
                os.unlink(os.path.join(work, f))
    shutil.rmtree(work, ignore_errors=True)

    print('[+] native loader written to %s' % out_dir)
    print('[+] run: python %s' % launcher)
    return 0


if __name__ == '__main__':
    sys.exit(main())

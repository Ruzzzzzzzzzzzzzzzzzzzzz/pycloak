#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys


def main():
    ap = argparse.ArgumentParser(description='Nuitka-harden a PyCloak payload')
    ap.add_argument('payload', help='protected .py produced by `pycloak build`')
    ap.add_argument('-o', '--out', default=None)
    ap.add_argument('--onefile', action='store_true', default=True, help='single-file exe (default)')
    ap.add_argument('--mingw64', action='store_true', help='use MinGW64 instead of MSVC')
    ap.add_argument('--console-disable', action='store_true', help='hide the console window')
    args, extra = ap.parse_known_args()

    out = args.out or os.path.splitext(os.path.abspath(args.payload))[0] + '.exe'
    cmd = [
        sys.executable, '-m', 'nuitka',
        '--onefile',
        '--standalone',
        '--output-filename=' + out,
        '--assume-yes-for-downloads',
        '--enable-plugin=anti-bloat',
        '--remove-output',
    ]
    if args.console_disable:
        cmd.append('--windows-console-mode=disable')
    if args.mingw64:
        cmd.append('--mingw64')
    cmd.append(args.payload)
    cmd.extend(extra)

    print('[*] running: %s' % ' '.join(cmd))
    try:
        subprocess.check_call(cmd)
    except FileNotFoundError:
        print('[!] nuitka not installed: pip install nuitka')
        return 1
    print('[+] executable written: %s' % out)
    print('[+] tip: ship license.key next to the exe (or embed with --license at build time)')
    return 0


if __name__ == '__main__':
    sys.exit(main())

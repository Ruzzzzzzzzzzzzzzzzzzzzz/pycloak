"""PyCloak command line interface."""

import argparse
import os
import sys

from . import __version__
from .builder import build, BuildError


def _cmd_build(args):
    try:
        info = build({
            'entry': args.app,
            'out': args.out,
            'vm': args.vm,
            'rename_params': args.rename_params,
            'flatten': args.flatten,
            'dead_code': args.dead_code,
            'anti_debug': args.anti_debug,
            'timing': args.timing,
            'pubkey': args.pubkey,
            'license': args.license,
            'banner': args.banner,
            'seed': args.seed,
            'pyz': args.pyz,
            'no_license': args.no_license,
        })
    except BuildError as e:
        print('[!] build failed: %s' % e)
        return 1
    print('[+] protected: %s' % info['out'])
    if info['pyz']:
        print('[+] zipapp:    %s' % info['pyz'])
    print('[+] modules:   %d (%s)' % (info['blobs'], ', '.join(info['modules'])))
    print('[+] strings:   %d encrypted' % info['strings'])
    print('[+] license:   %s' % info['license'])
    if info['author_key']:
        print('[+] author key: %s (move it off this machine, then delete)' % info['author_key'])
    if info['vm_functions']:
        print('[+] vm:        %s' % ', '.join(info['vm_functions']))
    for s in info['vm_skipped']:
        print('[!] vm skip:   %s (kept as ordinary blob)' % s)
    return 0


def _cmd_keygen(args):
    from .license_crypto import generate_keypair, private_key_pem, public_key_pem
    out_dir = args.out or 'keys'
    os.makedirs(out_dir, exist_ok=True)
    print('[*] generating %d-bit RSA keypair...' % args.bits)
    key = generate_keypair(bits=args.bits, seed=args.seed)
    priv_path = os.path.join(out_dir, 'key.pem')
    pub_path = os.path.join(out_dir, 'key.pub')
    with open(priv_path, 'w', encoding='utf-8') as f:
        f.write(private_key_pem(key))
    with open(pub_path, 'w', encoding='utf-8') as f:
        f.write(public_key_pem(key))
    print('[+] private key: %s (keep on the AUTHOR machine only)' % priv_path)
    print('[+] public key:  %s (passed to --pubkey at build time)' % pub_path)
    return 0


def _cmd_fingerprint(args):
    from .license_crypto import machine_fingerprint
    print(machine_fingerprint())
    return 0


def _cmd_sign(args):
    from .license_crypto import (parse_private_pem, machine_fingerprint,
                                 sign_sha256, make_payload, license_text)
    fp = args.fp
    if fp is None:
        fp = machine_fingerprint()
        print('[*] no --fp given, binding to this machine: %s' % fp)
    exp_ts = 0
    if args.expire:
        import datetime
        try:
            dt = datetime.datetime.strptime(args.expire, '%Y-%m-%d')
            exp_ts = int(dt.timestamp())
        except ValueError:
            print('[!] expire must look like 2027-01-01')
            return 1
    with open(args.key, 'r', encoding='utf-8') as f:
        key = parse_private_pem(f.read())
    payload = make_payload(fp, exp_ts)
    sig = sign_sha256(payload, key)
    out = args.out or 'license.key'
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write(license_text(payload, sig))
    print('[+] license written: %s (fp=%s, exp=%s)' % (out, fp, args.expire or 'never'))
    return 0


def _cmd_verify(args):
    from .license_crypto import (parse_public_pem, parse_license,
                                 verify_sha256, parse_payload)
    with open(args.pub, 'r', encoding='utf-8') as f:
        pub = parse_public_pem(f.read())
    with open(args.license, 'r', encoding='utf-8') as f:
        payload, sig = parse_license(f.read())
    ok = verify_sha256(payload, sig, pub['n'], pub['e'])
    if not ok:
        print('[!] signature INVALID')
        return 1
    exp, fp = parse_payload(payload)
    print('[+] signature valid (fp=%s, exp=%d)' % (fp, exp))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog='pycloak', description='PyCloak v%s - multi-layer Python obfuscator' % __version__)
    p.add_argument('--version', action='version', version='%(prog)s ' + __version__)
    sub = p.add_subparsers(dest='cmd', required=True)

    b = sub.add_parser('build', help='build a protected single-file payload')
    b.add_argument('app', help='entry script (its directory is scanned for local modules)')
    b.add_argument('-o', '--out', help='output file (default: <app>_protected.py)')
    b.add_argument('--vm', action='append', default=None,
                   help='module to VM-protect (repeatable; "mod" or "mod:func")')
    b.add_argument('--rename-params', action='store_true', help='rename function parameters too (breaks kwargs calls)')
    b.add_argument('--flatten', action='store_true', help='control-flow flattening on functions')
    b.add_argument('--dead-code', type=int, default=2, metavar='N', help='junk block intensity (default 2)')
    b.add_argument('--anti-debug', action='store_true', help='embed anti-debugging guard')
    b.add_argument('--timing', action='store_true', help='add timing-based debugger check')
    b.add_argument('--pubkey', metavar='PEM', help='RSA public key; enables license binding')
    b.add_argument('--license', metavar='FILE', help='embed a license file (per-customer build)')
    b.add_argument('--no-license', action='store_true',
                   help='disable license checking entirely (no guard code emitted)')
    b.add_argument('--banner', metavar='TEXT', help='header comment text')
    b.add_argument('--seed', type=int, default=None, help='deterministic RNG seed')
    b.add_argument('--pyz', action='store_true', help='also emit a zipapp .pyz')
    b.set_defaults(func=_cmd_build)

    k = sub.add_parser('keygen', help='generate RSA keypair')
    k.add_argument('-o', '--out', help='output directory (default: keys)')
    k.add_argument('-b', '--bits', type=int, default=2048, choices=(1024, 2048, 4096))
    k.add_argument('--seed', type=int, default=None)
    k.set_defaults(func=_cmd_keygen)

    f = sub.add_parser('fingerprint', help='print this machine fingerprint')
    f.set_defaults(func=_cmd_fingerprint)

    s = sub.add_parser('sign', help='issue a license')
    s.add_argument('-k', '--key', required=True, help='private key PEM')
    s.add_argument('-f', '--fp', default=None, help='target fingerprint ("*" = any machine)')
    s.add_argument('-e', '--expire', default=None, metavar='YYYY-MM-DD', help='expiry date')
    s.add_argument('-o', '--out', default='license.key')
    s.set_defaults(func=_cmd_sign)

    v = sub.add_parser('verify', help='verify a license against a public key')
    v.add_argument('-p', '--pub', required=True, help='public key PEM')
    v.add_argument('license', help='license file')
    v.set_defaults(func=_cmd_verify)

    args = p.parse_args(argv)
    sys.exit(args.func(args))


if __name__ == '__main__':
    main()

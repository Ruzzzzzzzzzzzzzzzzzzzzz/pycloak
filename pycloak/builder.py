"""Build orchestration: discovery, obfuscation, VM targeting, blob
encryption, license/guard wiring and two-pass loader rendering."""

import ast
import base64
import hashlib
import marshal
import os
import random
import sys
import types
import zlib

from . import aes_py
from . import stub_template
from . import vm_compiler
from . import vm_opcodes
from . import vm_runtime
from .anti_debug import STRINGS, STR_IDX, guard_source
from .ast_obfuscator import Obfuscator
from .license_crypto import (generate_keypair, license_text, make_payload,
                             parse_private_pem, parse_public_pem,
                             private_key_pem, sign_sha256)

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))

_XOR_KEY_LEN = 64
_NAME_KEY_LEN = 32
_GS_KEY_LEN = 32
_MAIN_KEY_LEN = 32


class BuildError(Exception):
    pass


def _rnd(seed=None):
    return random.Random(seed)


def _xor_bytes(data, key):
    return bytes(c ^ key[i % len(key)] for i, c in enumerate(data))


def _rot(b, r):
    return b[r:] + b[:r]


def make_segments(key, nseg, rot, rng):
    segs = [bytes(rng.randrange(256) for _ in key) for _ in range(nseg - 1)]
    v = segs[0]
    for s in segs[1:]:
        v = bytes(a ^ b for a, b in zip(_rot(v, rot), s))
    segs.append(bytes(a ^ b for a, b in zip(_rot(v, rot), key)))
    return segs


def _module_of(rel):
    parts = rel[:-3].replace(os.sep, '.').split('.')
    if parts[-1] == '__init__':
        parts = parts[:-1]
    return '.'.join(parts)


def collect_local_modules(base):
    mods = {}
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames
                       if not d.startswith('.') and d != '__pycache__']
        for f in filenames:
            if f.endswith('.py'):
                full = os.path.join(dirpath, f)
                mods[_module_of(os.path.relpath(full, base))] = full
    return mods


def _import_names(src):
    deps = set()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return deps
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                deps.add(a.name)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            deps.add(node.module)
    return deps


def discover(entry_path):
    base = os.path.dirname(os.path.abspath(entry_path))
    entry_name = _module_of(os.path.basename(entry_path))
    mods = collect_local_modules(base)
    if entry_name not in mods:
        raise BuildError('entry not found: %s' % entry_name)
    included = []
    seen = set()
    pending = [entry_name]
    while pending:
        m = pending.pop()
        if m in seen:
            continue
        seen.add(m)
        if m not in mods:
            continue
        included.append(m)
        with open(mods[m], 'r', encoding='utf-8', errors='replace') as f:
            src = f.read()
        for dep in _import_names(src):
            if dep in mods and dep not in seen:
                pending.append(dep)
            else:
                for mm in mods:
                    if mm.startswith(dep + '.') and mm not in seen:
                        pending.append(mm)
    return [(m, mods[m]) for m in included]


def _rewrite_main_guard(tree, flag_name):
    for node in tree.body:
        if isinstance(node, ast.If):
            t = node.test
            if (isinstance(t, ast.Compare) and isinstance(t.left, ast.Name)
                    and t.left.id == '__name__' and len(t.ops) == 1
                    and isinstance(t.ops[0], ast.Eq) and len(t.comparators) == 1
                    and isinstance(t.comparators[0], ast.Constant)
                    and t.comparators[0].value == '__main__'):
                t.left = ast.Name(id=flag_name, ctx=ast.Load())


def _parse_vm_specs(specs):
    out = {}
    for s in specs or []:
        if ':' in s:
            mod, fn = s.split(':', 1)
            out.setdefault(mod, set()).add(fn)
        else:
            out[s] = None
    return out


def _apply_vm(tree, targets, state, vmcall_name):
    ok = []
    skipped = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        if targets is not None and node.name not in targets:
            continue
        try:
            prog = vm_compiler.compile_function(node)
        except vm_compiler.VMUnsupported as e:
            skipped.append('%s (%s)' % (node.name, e))
            continue
        blob_id = len(state['vm_blobs'])
        state['vm_blobs'].append(marshal.dumps(
            (prog['code'], prog['consts'], prog['names'],
             prog['strtab'], prog['nlocals'])))
        ndef = len([d for d in prog['defaults'] if d is not None])
        argnames = prog['argnames']
        args = [ast.arg(arg=a) for a in argnames]
        defaults = [ast.Constant(value=d) for d in prog['defaults'][len(argnames) - ndef:]]
        wrapper = ast.FunctionDef(
            name=node.name,
            args=ast.arguments(
                posonlyargs=[], args=args, vararg=None,
                kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=defaults),
            body=[ast.Return(value=ast.Call(
                func=ast.Name(id=vmcall_name, ctx=ast.Load()),
                args=[
                    ast.Constant(value=blob_id),
                    ast.Tuple(elts=[ast.Name(id=a, ctx=ast.Load()) for a in argnames],
                              ctx=ast.Load()),
                    ast.Call(func=ast.Name(id='globals', ctx=ast.Load()), args=[], keywords=[]),
                ],
                keywords=[]))],
            decorator_list=[], returns=None, type_comment=None)
        idx = tree.body.index(node)
        tree.body[idx] = wrapper
        ok.append(node.name)
    return ok, skipped


def _build_aes_module(obf, main_key, s_name, dec_name):
    with open(os.path.join(_THIS_DIR, 'aes_py.py'), 'r', encoding='utf-8') as f:
        src = f.read()
    src += '\n\nKEY = bytes(%s)\n' % repr(list(main_key))
    src += 'ST = (\n'
    for s in obf.strings:
        src += "    '%s',\n" % aes_py.encrypt_blob(s.encode('utf-8'), main_key).hex()
    src += ')\n'
    src += 'CACHE = {}\n\n'
    src += 'def %s(i):\n' % s_name
    src += '    v = CACHE.get(i)\n'
    src += '    if v is None:\n'
    src += "        v = decrypt_blob(bytes.fromhex(ST[i]), KEY).decode('utf-8')\n"
    src += '        CACHE[i] = v\n'
    src += '    return v\n\n'
    src += 'def %s(data):\n' % dec_name
    src += '    return decrypt_blob(data, KEY)\n'
    return src


def _gs_call(gsf_name, idx):
    return '%s(%d)' % (gsf_name, idx)


def _exit_src(tn, osn, code, ind):
    return ('%stry:\n' % ind
            + '%s    %s.sleep(2 + (%d %% 7))\n' % (ind, tn, code)
            + '%sexcept Exception:\n' % ind
            + '%s    pass\n' % ind
            + '%s%s._exit(0)\n' % (ind, osn))


def _ver_src(n, pubhex):
    return '''{di} = bytes.fromhex('3031300d060960864801650304020105000420')

def {ver}({m}, {s}, {n}, {e}):
    {k} = ({n}.bit_length() + 7) // 8
    {m0} = pow(int.from_bytes({s}, 'big'), {e}, {n}).to_bytes({k}, 'big')
    {t} = b'\\x00\\x01' + b'\\xff' * ({k} - 51 - 3) + b'\\x00' + {di} + hashlib.sha256({m}).digest()
    return hmac.compare_digest({m0}, {t})

{pn} = int('{pubhex}', 16)
{pe} = 65537
'''.format(di=n['di'], ver=n['ver'], m=n['m'], s=n['s'], n=n['n'], e=n['e'],
           k=n['k'], m0=n['m0'], t=n['t'], pn=n['pn'], pubhex=pubhex, pe=n['pe'])


def _licv_src(n, embed_lic):
    gs = lambda i: _gs_call(n['gsf'], i)  # noqa: E731
    return '''def {licv}():
    {txt} = None
    {p0} = {osn}.environ.get({gs13})
    if {p0} and {osn}.path.exists({p0}):
        {txt} = open({p0}, 'r', encoding={gs14}, errors={gs15}).read()
{embed}
    if {txt} is None:
        {c0} = {osn}.path.join({osn}.path.dirname({osn}.path.abspath(sys.argv[0])), {gs12})
        if {osn}.path.exists({c0}):
            {txt} = open({c0}, 'r', encoding={gs14}, errors={gs15}).read()
    if {txt} is None:
        {c1} = {osn}.path.join({osn}.getcwd(), {gs12})
        if {osn}.path.exists({c1}):
            {txt} = open({c1}, 'r', encoding={gs14}, errors={gs15}).read()
    if {txt} is None:
        return None
    try:
        {pl} = None
        {sg} = None
        for {ln} in {txt}.strip().splitlines():
            if {ln}.startswith({gs16}):
                {pl} = base64.b64decode({ln}[8:])
            elif {ln}.startswith({gs17}):
                {sg} = base64.b64decode({ln}[4:])
        if not {pl} or not {sg}:
            return None
        if not {ver}({pl}, {sg}, {pn}, {pe}):
            return None
        {fs} = {pl}.decode().split({gs20})
        if len({fs}) != 3 or {fs}[0] != {gs18}:
            return None
        if int({fs}[1]) and {tn}.time() > int({fs}[1]):
            return None
        return {fs}[2]
    except Exception:
        return None
'''.format(
        licv=n['licv'], txt=n['txt'], p0=n['p0'], osn=n['osn'],
        gs12=gs(STR_IDX['license_key']), gs13=gs(STR_IDX['license_env']),
        gs14=gs(STR_IDX['utf8']), gs15=gs(STR_IDX['errors_ignore']),
        gs16=gs(STR_IDX['payload_prefix']), gs17=gs(STR_IDX['sig_prefix']),
        gs18=gs(STR_IDX['magic']), gs20=gs(STR_IDX['sep']),
        c0=n['c0'], c1=n['c1'], pl=n['pl'], sg=n['sg'], ln=n['ln'],
        ver=n['ver'], pn=n['pn'], pe=n['pe'], fs=n['fs'], tn=n['tn'],
        embed=embed_lic)


def _licb_src(n):
    gs = lambda i: _gs_call(n['gsf'], i)  # noqa: E731
    return '''def {licb}({fpx}):
    if {fpx} == {gs19}:
        return True
    try:
        {u} = getpass.getuser()
    except Exception:
        {u} = {osn}.environ.get({gs21}, {gs22})
    {p} = (uuid.getnode(), platform.node(), platform.machine(), {u}, platform.system())
    {f} = hashlib.sha256({gs20}.join(str({v2}) for {v2} in {p}).encode()).hexdigest()
    return {f} == {fpx}
'''.format(
        licb=n['licb'], fpx=n['fpx'], gs19=gs(STR_IDX['wildcard']),
        u=n['u'], osn=n['osn'], gs21=gs(STR_IDX['username']),
        gs22=gs(STR_IDX['unknown']), p=n['p'], f=n['f'],
        gs20=gs(STR_IDX['sep']), v2=n['v2'])


def _intg_src(n, target_fns, hashes, rng):
    lines = ['def %s():' % n['intg']]
    for idx, fname in enumerate(target_fns):
        h = hashes[fname]
        masks = [rng.randrange(1, 256) for _ in range(32)]
        parts = ', '.join('%d ^ %d' % (h[i] ^ masks[i], masks[i]) for i in range(32))
        hv = n['h%d' % idx]
        lines.append('    %s = hashlib.sha256(%s.__code__.co_code).digest()' % (hv, fname))
        lines.append('    if %s != bytes((%s,)):' % (hv, parts))
        lines.append('        try:')
        lines.append('            %s.sleep(2 + (%d %% 7))' % (n['tn'], 61 + idx))
        lines.append('        except Exception:')
        lines.append('            pass')
        lines.append('        %s._exit(0)' % n['osn'])
    return '\n'.join(lines) + '\n'


def build(cfg):
    rng = _rnd(cfg.get('seed'))
    modules = discover(cfg['entry'])
    entry_name = modules[0][0]

    N = {}
    for key in ('osn', 'tn', 'mr', 'zl', 'il', 'iu', 'ia', 'kj', 's', 'v', 'x',
                'r', 'a', 'b', 'xk', 'xks', 'nk', 'nks', 'xdec', 'd', 'c', 'i',
                'boot', 'hk', 'bb', 'gsk', 'gsks', 'gst', 'gsc', 'gsf', 'c2',
                'j', 'intg', 'licv', 'licb', 'pn', 'pe', 'ver', 'di', 'm', 'k',
                'e', 'm0', 't', 'txt', 'p0', 'c0', 'c1', 'pl', 'sg', 'ln', 'fs',
                'fpx', 'u', 'p', 'v2', 'f', 'gtrace', 'gos', 'genv', 'gm',
                'gct', 'gk', 'gbuf', 'gop', 'gtpat', 'gneg', 'gt0', 'gacc',
                'gi', 'pay', 'blbs', 'vmb', 'decf', 'sfn', 'vmcf', 'vmdec',
                'hkl', 'loadb', 'name', 'inj', 'asmain', 'ct', 'raw', 'mm',
                'ns', 'sp', 'n', 'pp', 'tt', 'raw0', 'm0', 'vns', 'bootf',
                'entryn', 'vmmodn', 'h0', 'h1', 'h2', 'h3', 'h4', 'h5', 'vv',
                'mainflag'):
        N[key] = '_%s%04x' % (key[:2], rng.randrange(0x10000))
    N['s_name'] = '_s%04x' % rng.randrange(0x10000)
    N['dec_name'] = '_dc%04x' % rng.randrange(0x10000)
    N['vmcall_name'] = '_vc%04x' % rng.randrange(0x10000)
    N['vmmod_name'] = '_rt_%04x' % rng.randrange(0x10000)

    main_key = bytes(rng.randrange(256) for _ in range(_MAIN_KEY_LEN))
    xor_key = bytes(rng.randrange(256) for _ in range(_XOR_KEY_LEN))
    name_key = bytes(rng.randrange(256) for _ in range(_NAME_KEY_LEN))
    gs_key = bytes(rng.randrange(256) for _ in range(_GS_KEY_LEN))

    rot = rng.randrange(1, 16)
    xk_segs = make_segments(xor_key, 3, rot, rng)
    nk_segs = make_segments(name_key, 3, rot, rng)
    gsk_segs = make_segments(gs_key, 2, rot, rng)

    gst_strings = list(STRINGS) + [entry_name, N['vmmod_name']]
    gst_hex = [_xor_bytes(s.encode('utf-8'), gs_key).hex() for s in gst_strings]

    obf = Obfuscator(
        rng=rng,
        rename_params=cfg.get('rename_params', False),
        dead_code=int(cfg.get('dead_code', 0)),
        flatten=cfg.get('flatten', False))
    obf.s_func = N['s_name']
    if obf.flatten_enabled:
        obf.sentinel = obf.fresh_name('_sn_')

    vm_specs = _parse_vm_specs(cfg.get('vm') or [])
    state = {'vm_blobs': []}
    blobs = {}
    vm_ok, vm_skipped = [], []

    for name, path in modules:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            src = f.read()
        tree = ast.parse(src)
        if name in vm_specs:
            ok, skipped = _apply_vm(tree, vm_specs[name], state, N['vmcall_name'])
            vm_ok.extend('%s:%s' % (name, f) for f in ok)
            vm_skipped.extend('%s:%s' % (name, f) for f in skipped)
        if name == entry_name:
            _rewrite_main_guard(tree, N['mainflag'])
        if obf.flatten_enabled:
            tree.body.insert(0, ast.Assign(
                targets=[ast.Name(id=obf.sentinel, ctx=ast.Store())],
                value=ast.Call(func=ast.Name(id='object', ctx=ast.Load()), args=[], keywords=[])))
        obf.process(tree)
        fake_name = '<%s:%s>' % (name, '%04x' % rng.randrange(0x10000))
        code = compile(tree, fake_name, 'exec')
        payload = zlib.compress(marshal.dumps(code))
        blobs[name] = base64.b64encode(
            aes_py.encrypt_blob(payload, main_key)).decode('ascii')

    rt_src = vm_runtime.module_source(vm_opcodes.runtime_constants_source())
    rt_code = compile(rt_src, '<vmrt:%s>' % ('%04x' % rng.randrange(0x10000)), 'exec')
    blobs[N['vmmod_name']] = base64.b64encode(
        aes_py.encrypt_blob(zlib.compress(marshal.dumps(rt_code)), main_key)).decode('ascii')

    aes_src = _build_aes_module(obf, main_key, N['s_name'], N['dec_name'])
    aes_code = compile(aes_src, '<aescore>', 'exec')
    boot_blob = base64.b64encode(
        _xor_bytes(zlib.compress(marshal.dumps(aes_code)), xor_key)).decode('ascii')

    named = {hashlib.sha256(n.encode()).digest()[:8]: ct for n, ct in blobs.items()}

    lic_enabled = False
    pub_hex = '1'
    embed_lic = ''
    author_key_path = None
    out_path = cfg.get('out') or (os.path.splitext(cfg['entry'])[0] + '_protected.py')
    if cfg.get('no_license'):
        lic_enabled = False
    elif cfg.get('pubkey'):
        with open(cfg['pubkey'], 'r', encoding='utf-8') as f:
            pub = parse_public_pem(f.read())
        pub_hex = '%x' % pub['n']
        lic_enabled = True
        if cfg.get('license'):
            with open(cfg['license'], 'r', encoding='utf-8') as f:
                embed_lic = '    if %s is None:\n        %s = %r\n' % (
                    N['txt'], N['txt'], f.read())
    else:
        author_key_path = os.path.splitext(out_path)[0] + '.author.key'
        if os.path.exists(author_key_path):
            with open(author_key_path, 'r', encoding='utf-8') as f:
                key = parse_private_pem(f.read())
        else:
            key = generate_keypair(bits=2048, seed=cfg.get('seed'))
            os.makedirs(os.path.dirname(os.path.abspath(author_key_path)), exist_ok=True)
            with open(author_key_path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(private_key_pem(key))
        pub_hex = '%x' % key['n']
        lic_enabled = True
        payload = make_payload('*', 0)
        sig = sign_sha256(payload, key)
        embed_lic = '    if %s is None:\n        %s = %r\n' % (
            N['txt'], N['txt'], license_text(payload, sig))

    gs = lambda i: _gs_call(N['gsf'], i)  # noqa: E731
    guard_n = {
        'gtrace': N['gtrace'], 'gos': N['gos'], 'genv': N['genv'],
        'tn': N['tn'], 'osn': N['osn'], 'm': N['gm'], 'ct': N['gct'],
        'il': N['il'], 'k': N['gk'], 'buf': N['gbuf'], 'op': N['gop'],
        'tpat': gs(STR_IDX['trace_pat']) + '.encode()',
        'neg': gs(STR_IDX['trace_neg']) + '.encode()',
        't0': N['gt0'], 'acc': N['gacc'], 'i': N['gi'],
        'gs0': gs(STR_IDX['ctypes']), 'gs1': gs(STR_IDX['win32']),
        'gs2': gs(STR_IDX['linux']), 'gs4': gs(STR_IDX['proc_status']),
        'gs5': gs(STR_IDX['pydevd']), 'gs6': gs(STR_IDX['debugpy']),
        'gs7': gs(STR_IDX['pydevd_bundle']), 'gs8': gs(STR_IDX['pydevd_frame']),
        'gs9': gs(STR_IDX['pdb']), 'gs10': gs(STR_IDX['pybreakpoint']),
        'gs11': gs(STR_IDX['builtins_breakpoint']),
    }
    guard_blk = guard_source(guard_n, timing=bool(cfg.get('timing')))

    pre = mid = post = ''
    glic_block = ''
    if lic_enabled:
        glic_block = (guard_blk + '\n' + _ver_src(N, pub_hex) + '\n'
                      + _licv_src(N, embed_lic) + '\n' + _licb_src(N) + '\n')
        pre = ('    %s()\n' % N['intg']
               + '    %s()\n' % N['gtrace']
               + '    %s = %s()\n' % (N['pay'], N['licv'])
               + '    if %s is None:\n' % N['pay']
               + _exit_src(N['tn'], N['osn'], 9, '        '))
        mid = '    %s()\n' % N['gos']
        post = ('    %s()\n' % N['genv']
                + '    if not %s(%s):\n' % (N['licb'], N['pay'])
                + _exit_src(N['tn'], N['osn'], 10, '        ')
                + '    %s()\n' % N['gtrace'])

    if lic_enabled:
        intg_targets = [N['licv'], N['licb'], N['gtrace'], N['gos'], N['genv'], N['bootf']]
    else:
        intg_targets = [N['bootf']]

    entryn = _gs_call(N['gsf'], 25)
    vmmodn = _gs_call(N['gsf'], 26)

    cfg_out = dict(N)
    cfg_out.update({
        'banner': cfg.get('banner', 'PyCloak protected payload - redistribution prohibited'),
        'r': str(rot),
        'xks': repr(tuple(bytes(s) for s in xk_segs)),
        'nks': repr(tuple(bytes(s) for s in nk_segs)),
        'gsks': repr(tuple(bytes(s) for s in gsk_segs)),
        'bootb': "'%s'" % boot_blob,
        'gstlit': repr(tuple(gst_hex)),
        'gs14': gs(STR_IDX['utf8']),
        'glic_block': glic_block,
        'blbslit': repr(named),
        'vmblit': repr([base64.b64encode(
            aes_py.encrypt_blob(zlib.compress(b), main_key)).decode('ascii')
            for b in state['vm_blobs']]),
        'sname': N['s_name'], 'vmname': N['vmcall_name'],
        'decn': N['dec_name'],
        'pre': pre, 'mid': mid, 'post': post,
        'entryn': entryn,
        'vmmodn': vmmodn,
        'intg_src': '# placeholder\n',
    })

    text1 = stub_template.render(cfg_out)
    tree1 = ast.parse(text1)
    hashes = {}
    whole_code = compile(text1, '<stub>', 'exec')
    for c in whole_code.co_consts:
        if isinstance(c, types.CodeType) and c.co_name in intg_targets:
            hashes[c.co_name] = hashlib.sha256(c.co_code).digest()
    missing = [t for t in intg_targets if t not in hashes]
    if missing:
        raise BuildError('integrity targets missing from stub: %s' % missing)

    cfg_out['intg_src'] = _intg_src(N, intg_targets, hashes, rng)
    stub = stub_template.render(cfg_out)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(stub)

    info = {
        'out': out_path, 'pyz': None,
        'modules': [m for m, _ in modules],
        'strings': len(obf.strings),
        'vm_functions': vm_ok, 'vm_skipped': vm_skipped,
        'blobs': len(blobs),
        'license': 'embedded' if (lic_enabled and cfg.get('license')) else
                   ('author-key' if lic_enabled else 'disabled'),
        'author_key': author_key_path,
    }
    if cfg.get('pyz'):
        pyz_path = os.path.splitext(out_path)[0] + '.pyz'
        import zipfile
        with zipfile.ZipFile(pyz_path, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('__main__.py', stub)
        info['pyz'] = pyz_path
    return info

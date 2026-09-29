"""Split anti-debugging checkpoints with inline exits and a plaintext string table."""

STR_IDX = {
    'ctypes': 0,
    'win32': 1,
    'linux': 2,
    'darwin': 3,
    'proc_status': 4,
    'pydevd': 5,
    'debugpy': 6,
    'pydevd_bundle': 7,
    'pydevd_frame': 8,
    'pdb': 9,
    'pybreakpoint': 10,
    'builtins_breakpoint': 11,
    'license_key': 12,
    'license_env': 13,
    'utf8': 14,
    'errors_ignore': 15,
    'payload_prefix': 16,
    'sig_prefix': 17,
    'magic': 18,
    'wildcard': 19,
    'sep': 20,
    'username': 21,
    'unknown': 22,
    'trace_pat': 23,
    'trace_neg': 24,
}

STRINGS = [
    'ctypes', 'win32', 'linux', 'darwin', '/proc/self/status',
    'pydevd', 'debugpy', '_pydevd_bundle', 'pydevd_frame_evaluator', 'pdb',
    'PYTHONBREAKPOINT', 'builtins.breakpoint', 'license.key', 'PYCLOAK_LICENSE',
    'utf-8', 'ignore', 'payload=', 'sig=', 'pycloak1', '*', '|',
    'USERNAME', 'unknown', 'TracerPid', 'TracerPid:\t0',
]


def _exit_block(n, tname, osname, ind='    '):
    return (
        '%stry:\n' % ind
        + '%s    %s.sleep(2 + (%d %% 7))\n' % (ind, tname, n)
        + '%sexcept Exception:\n' % ind
        + '%s    pass\n' % ind
        + '%s%s._exit(0)\n' % (ind, osname)
    )


def guard_trace(n):
    return '''def {gtrace}():
    try:
        if sys.gettrace() is not None:
{exit31}
    except Exception:
        pass
    for {m} in ({gs5}, {gs6}, {gs7}, {gs8}, {gs9}):
        if {m} in sys.modules:
{exit34}
'''.format(
        gtrace=n['gtrace'], gs5=n['gs5'], gs6=n['gs6'], gs7=n['gs7'],
        gs8=n['gs8'], gs9=n['gs9'], m=n['m'],
        exit31=_exit_block(31, n['tn'], n['osn'], ind='            '),
        exit34=_exit_block(34, n['tn'], n['osn'], ind='            '),
    )


def guard_os(n):
    return '''def {gos}():
    try:
        if sys.platform == {gs1}:
            {ct} = {il}.import_module({gs0})
            {k} = {ct}.windll.kernel32
            if {k}.IsDebuggerPresent() or {k}.CheckRemoteDebuggerPresent(-1):
{exit32}
        elif sys.platform == {gs2}:
            {buf} = {op}({gs4}, 'rb').read()
            if {tpat} in {buf} and {neg} not in {buf}:
{exit33}
    except Exception:
        pass
'''.format(
        gos=n['gos'], gs1=n['gs1'], gs2=n['gs2'], gs4=n['gs4'], gs0=n['gs0'],
        ct=n['ct'], il=n['il'], k=n['k'], buf=n['buf'], op=n['op'],
        tpat=n['tpat'], neg=n['neg'],
        exit32=_exit_block(32, n['tn'], n['osn'], ind='                '),
        exit33=_exit_block(33, n['tn'], n['osn'], ind='                '),
    )


def guard_env(n, timing=False):
    timing_src = ''
    if timing:
        timing_src = '''    {t0} = {tn}.perf_counter()
    {acc} = 0
    for {i} in range(300000):
        {acc} = ({acc} + {i}) ^ 0x5A17
    if {tn}.perf_counter() - {t0} > 1.2:
{exit36}
'''.format(
            t0=n['t0'], tn=n['tn'], acc=n['acc'], i=n['i'],
            exit36=_exit_block(36, n['tn'], n['osn'], ind='            '))
    return '''def {genv}():
    try:
        if {osn}.environ.get({gs10}) not in (None, '', {gs11}):
{exit35}
    except Exception:
        pass
{timing}
'''.format(
        genv=n['genv'], osn=n['osn'], gs10=n['gs10'], gs11=n['gs11'],
        exit35=_exit_block(35, n['tn'], n['osn'], ind='            '), timing=timing_src,
    )


def guard_source(n, timing=False):
    return (guard_trace(n) + '\n' + guard_os(n) + '\n' + guard_env(n, timing))

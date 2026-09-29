"""Renders the final single-file loader."""

_TEMPLATE = r'''# -*- coding: utf-8 -*-
# $BANNER$
import sys
import os as $OSN$
import time as $TN$
import marshal as $MR$
import zlib as $ZL$
import base64
import hashlib
import hmac
import uuid
import platform
import getpass
import importlib as $IL$
import importlib.util as $IU$
import importlib.abc as $IA$

def $KJ$($S$):
    $V$ = $S$[0]
    for $X$ in $S$[1:]:
        $V$ = $V$[$R$:] + $V$[:$R$]
        $V$ = bytes($A$ ^ $B$ for $A$, $B$ in zip($V$, $X$))
    return $V$

$XK$ = $KJ$($XKS$)
$NK$ = $KJ$($NKS$)

def $XDEC$($D$):
    return bytes($C$ ^ $XK$[$I$ % len($XK$)] for $I$, $C$ in enumerate($D$))

$BOOT$ = ($BOOTB$,)

def $HK$($B$):
    return hashlib.sha256($B$).digest()[:8]

$GSK$ = $KJ$($GSKS$)
$GST$ = ($GSTLIT$)
$GSC$ = {}

def $GSF$($I$):
    $V$ = $GSC$.get($I$)
    if $V$ is None:
        $V$ = bytes($C2$ ^ $GSK$[$J$ % len($GSK$)] for $J$, $C2$ in enumerate(bytes.fromhex($GST$[$I$]))).decode()
        $GSC$[$I$] = $V$
    return $V$

$INTG_SRC$

$GLIC_BLOCK$

$BLBS$ = $BLBSLIT$
$VMB$ = $VMBLIT$

$DECF$ = None
$SFN$ = None
$VMCF$ = None

def $VMDEC$($I$):
    return $ZL$.decompress($DECF$(base64.b64decode($VMB$[$I$])))

class $HKL$($IA$.MetaPathFinder, $IA$.Loader):
    def find_spec(self, $N$, $P$=None, $T$=None):
        if $HK$($N$.encode()) in $BLBS$:
            return $IU$.spec_from_loader($N$, self)
    def create_module(self, $SP$):
        return None
    def exec_module(self, $M$):
        $LOADB$($M$.__name__)

def $LOADB$($NAME$, $INJ$=None, $ASMAIN$=False):
    $CT$ = $BLBS$[$HK$($NAME$.encode())]
    $RAW$ = $ZL$.decompress($DECF$(base64.b64decode($CT$)))
    $M$ = sys.modules.get($NAME$)
    if $M$ is None:
        $M$ = $IU$.module_from_spec($IU$.spec_from_loader($NAME$, $HKL$()))
        sys.modules[$NAME$] = $M$
    $D$ = $M$.__dict__
    $D$['$SNAME$'] = $SFN$
    $D$['$VMNAME$'] = $VMCF$
    if $INJ$:
        $D$.update($INJ$)
    if $ASMAIN$:
        $D$['$MAINFLAG$'] = __name__
    $D$['__file__'] = $NAME$ + '.pyc'
    exec($MR$.loads($RAW$), $D$)
    return $D$

def $BOOTF$():
    global $DECF$, $SFN$, $VMCF$
$PRE$
    $RAW0$ = $ZL$.decompress($XDEC$(base64.b64decode($BOOT$[0])))
    $M0$ = $IU$.module_from_spec($IU$.spec_from_loader('__aescore__', None))
    exec($MR$.loads($RAW0$), $M0$.__dict__)
    sys.modules['__aescore__'] = $M0$
    $DECF$ = $M0$.__dict__['$DECN$']
    $SFN$ = $M0$.__dict__['$SNAME$']
$MID$
    $VNS$ = $LOADB$($VMMODN$, {'_VM_DEC': $VMDEC$})
    $VMCF$ = $VNS$['_vm_call']
$POST$
    sys.meta_path.append($HKL$())
    $LOADB$($ENTRYN$, None, True)

$BOOTF$()
'''

import re

_PLACEHOLDER = re.compile(r'\$[A-Z0-9_]+\$')


def render(cfg):
    def sub(m):
        key = m.group(0)[1:-1].lower()
        if key not in cfg:
            raise KeyError('missing stub cfg key: %s' % key)
        return str(cfg[key])

    return _PLACEHOLDER.sub(sub, _TEMPLATE)

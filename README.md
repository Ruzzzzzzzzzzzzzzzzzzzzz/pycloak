# PyCloak

Multi-layer Python obfuscator: AST obfuscation (incl. MBA) → AES string
encryption → AES+zlib bytecode encryption → custom import hook → XOR native
bootstrap → multi-point anti-debug → integrity self-check → RSA license
binding → custom VM for critical functions. Zero third-party dependencies
(build and runtime use only the standard library). Ships with a Tkinter GUI
(Chinese/English switchable).

## Quick start

```powershell
# GUI (recommended)
python pycloak_gui.py

# or CLI
python -m pycloak.cli build examples/app.py -o dist/app_protected.py `
    --vm payment_core --flatten --rename-params --dead-code 3 --anti-debug

# License workflow (buttons exist in the GUI too)
python gen_license.py keygen -o keys -b 2048
python gen_license.py fingerprint          # run on the customer machine
python gen_license.py sign -k keys/key.pem -f <FP> -e 2027-12-31 -o license.key
python -m pycloak.cli build examples/app.py -o dist/app.py `
    --vm payment_core --anti-debug --pubkey keys/key.pub --license license.key
```

Three license modes:

- Default (author key): each build auto-generates a 2048-bit keypair and
  embeds a `*` wildcard license; the private key is written to
  `<output>.author.key` (move it away, then delete it). Rebuilds to the same
  output path reuse that key.
- `--pubkey PEM`: bind to a fixed public key; optional `--license FILE` for
  per-customer embedding.
- `--no-license`: emit no check code at all (no dead-code artifacts).

## Architecture

```
plaintext stub (single-file artifact)
├─ split-key recombination (XOR/name/string keys each split into 2-3
│    fragments, recombined at runtime via rotation + XOR)
├─ plaintext string table (all guard/license strings XOR-encrypted;
│    no 'pydevd'/'TracerPid' in cleartext)
├─ integrity self-check: SHA-256 over the co_code of the lic/guard/boot
│    functions (hashes embedded byte-wise XOR-masked and scattered);
│    any patch to the plaintext layer triggers a delayed silent exit
├─ three anti-debug checkpoints (trace/modules, OS debugger, environment)
│    spread through the boot flow, each embedding its own delayed exit
│    (no single patchable fail function)
├─ two-stage license check: signature+expiry → AES layer loads → fingerprint
├─ module names keyed by SHA-256 prefix (no reversible XOR names) +
│    meta_path importer
├─ layer 0: AES core (XOR+zlib) - AES-256-CBC + string table + _s()
├─ layer 1: custom VM interpreter (AES+zlib) - 47-opcode stack machine
├─ layer 2: business modules (AES+zlib marshalled pyc)
└─ layer 3: VM programs (private bytecode for critical functions)
```

## Protection layers

1. **AST obfuscation**: scope-aware renaming (parameters optional), integer
   rewriting into equivalent expressions (arithmetic decomposition / MBA
   `(v^M)^M` / `(v&M)+(v&~M)` with random nesting), opaque-predicate dead
   code, control-flow flattening into a state machine (randomized block
   order and IDs; branch targets fully tracked through cond blocks).
2. **String encryption**: business strings via the AES layer `_s(idx)`;
   plaintext-layer strings via the XOR split table `_gs(idx)`.
3. **Bytecode encryption**: compile → marshal → zlib → AES-256-CBC; the
   meta_path importer decrypts in memory at import time - no pyc ever hits
   the disk.
4. **Custom VM**: functions named by `--vm` compile to private 47-opcode
   stack-machine bytecode; the interpreter itself is an encrypted blob;
   unsupported syntax falls back to ordinary protection with a warning.
5. **License**: RSA-2048 PKCS#1 v1.5 SHA-256 (keygen optimized: 168-prime
   trial division + 16 fixed Miller-Rabin bases, ~0.3s for 2048 bits);
   fingerprint binding, expiry, `*` wildcard; only the public key ships.
6. **Anti-debug**: three distributed checkpoints with independent delayed
   exits; fully randomized naming; optional timing check.
7. **Integrity self-check**: co_code SHA-256 for plaintext-layer functions,
   hashes byte-masked and scattered; patching any check logic trips it.
8. **Native hardening** (optional): `build_cython.py` / `build_nuitka.py`,
   one click from the GUI.

## Multiprocessing support

Spawned child processes re-execute the loader entry; the entry module's
`if __name__ == '__main__'` guard is rewritten to read an injected flag, so
the main block stays dormant in children (`'__mp_main__'`), while function
`__module__` attributes keep the real module name for pickle. VM-protected
worker functions execute correctly in `ProcessPoolExecutor` subprocesses
(covered by `examples/mp_demo.py`).

## Known limits

- Artifacts are bound to the Python version they were built with (marshal
  is not cross-version).
- `--rename-params` breaks keyword-argument calls; module-level function and
  class names are not renamed by default so cross-module imports keep
  working.
- Flattening skips functions containing `yield`/`async`; the VM rejects
  nested functions, closures, decorators, try/with/match and
  `*args`/`**kwargs` (automatic fallback).
- The plaintext-layer self-check and anti-debug can still be defeated in
  pure Python by a double patch (edit code + recompute hashes); to counter
  that level, compile with Cython/Nuitka so the plaintext layer disappears.

## Layout

```
pycloak/
├── pycloak/            # obfuscator core (aes/vm/ast/license/stub/builder/cli)
├── pycloak_gui.py      # Tkinter console (build/license/native hardening/log,
│                       #   Chinese/English switchable)
├── gen_license.py      # keygen / fingerprint / sign / verify
├── build_cython.py     # Cython native hardening
├── build_nuitka.py     # Nuitka onefile exe
└── examples/           # demos (app + utils + payment_core + mp_demo)
```

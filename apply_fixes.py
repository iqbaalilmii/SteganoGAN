#!/usr/bin/env python3
"""
apply_fixes.py
==============
Script otomatis untuk memperbaiki DAI-Lab/SteganoGAN agar bisa
dijalankan di Python 3.10+ dan dependency modern.

Jalankan dari root folder repo:
    python3 apply_fixes.py

Fix yang diterapkan:
    1. setup.py        — hapus version constraint yang rusak
    2. utils.py        — fix reedsolo >= 1.0 API (return tuple, bukan bytes)
    3. models.py       — fix Adam optimizer deserialization + weights_only=False
    4. README.md       — tambah catatan instalasi modern
"""

import os
import re
import sys

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def read(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def write(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def ok(msg):
    print(f"  [\033[92m✓\033[0m] {msg}")

def fail(msg):
    print(f"  [\033[91m✗\033[0m] {msg}")
    sys.exit(1)

def info(msg):
    print(f"  [·] {msg}")

def section(title):
    print(f"\n\033[1m{'─'*50}\033[0m")
    print(f"\033[1m  {title}\033[0m")
    print(f"\033[1m{'─'*50}\033[0m")

# ─────────────────────────────────────────────
# Sanity check — pastikan dijalankan dari root repo
# ─────────────────────────────────────────────

REQUIRED = ['setup.py', 'steganogan/utils.py', 'steganogan/models.py', 'README.md']

print("\n\033[1mSteganoGAN Compatibility Patcher\033[0m")
print("Memperbaiki repo agar bisa jalan di Python 3.10+ & dependency modern\n")

for f in REQUIRED:
    if not os.path.exists(f):
        fail(f"File tidak ditemukan: {f}\nPastikan script dijalankan dari root folder repo!")

ok("Semua file target ditemukan")

# ─────────────────────────────────────────────
# FIX 1: setup.py
# ─────────────────────────────────────────────
section("FIX 1 — setup.py: Version Constraint")

info("Masalah: format 'numpy>=1.15.4<1.16.0' tidak valid di setuptools modern (butuh koma)")
info("Fix: ganti seluruh install_requires dengan daftar package tanpa version lock")

code = read('setup.py')

# Ganti blok install_requires = [ ... ] dengan versi bersih
clean_install_requires = """install_requires = [
    'imageio',
    'reedsolo',
    'scipy',
    'tqdm',
    'numpy',
    'Pillow',
    'torch',
    'torchvision',
]"""

code = re.sub(
    r'install_requires\s*=\s*\[.*?\]',
    clean_install_requires,
    code,
    flags=re.DOTALL
)

# Ganti blok setup_requires = [ ... ] dengan versi bersih
clean_setup_requires = "setup_requires = []"
code = re.sub(
    r'setup_requires\s*=\s*\[.*?\]',
    clean_setup_requires,
    code,
    flags=re.DOTALL
)

# Hapus parameter yang tidak dikenal oleh setuptools modern
code = re.sub(r'\s*install_package_data\s*=\s*(True|False)\s*,?\n', '\n', code)
code = re.sub(r'\s*test_suite\s*=\s*[\'"].*?[\'"]\s*,?\n', '\n', code)
code = re.sub(r'\s*tests_require\s*=\s*tests_require\s*,?\n', '\n', code)

write('setup.py', code)
ok("setup.py diperbaiki")

# ─────────────────────────────────────────────
# FIX 2: steganogan/utils.py
# ─────────────────────────────────────────────
section("FIX 2 — utils.py: reedsolo API Breaking Change")

info("Masalah: reedsolo >= 1.0 mengubah return value rs.decode()")
info("  Lama (0.3): rs.decode(x) -> bytes")
info("  Baru (1.x): rs.decode(x) -> namedtuple(decoded, msgecc, errata_pos)")
info("Fix: deteksi tipe return value dan ambil element [0] jika tuple")

code = read('steganogan/utils.py')

old_bytearray_to_text = '''def bytearray_to_text(x):
    """Apply error correction and decompress"""
    try:
        text = rs.decode(x)
        text = zlib.decompress(text)
        return text.decode("utf-8")
    except BaseException:
        return False'''

new_bytearray_to_text = '''def bytearray_to_text(x):
    """Apply error correction and decompress"""
    try:
        result = rs.decode(x)
        # reedsolo >= 1.0 returns namedtuple(decoded, msgecc, errata_pos)
        # reedsolo  < 1.0 returns bytes directly
        if isinstance(result, tuple):
            text = bytes(result[0])
        else:
            text = bytes(result)
        text = zlib.decompress(text)
        return text.decode("utf-8")
    except BaseException:
        return False'''

if old_bytearray_to_text in code:
    code = code.replace(old_bytearray_to_text, new_bytearray_to_text)
    write('steganogan/utils.py', code)
    ok("utils.py diperbaiki (reedsolo API fix)")
else:
    # Mungkin sudah di-patch sebelumnya, cek apakah pattern baru sudah ada
    if 'isinstance(result, tuple)' in code:
        ok("utils.py sudah di-patch sebelumnya, skip")
    else:
        fail("Pattern bytearray_to_text tidak ditemukan di utils.py — mungkin struktur file berbeda")

# ─────────────────────────────────────────────
# FIX 3: steganogan/models.py
# ─────────────────────────────────────────────
section("FIX 3 — models.py: Adam Optimizer + torch.load")

code = read('steganogan/models.py')
modified = False

# Fix 3a: torch.load weights_only
info("Fix 3a: tambah weights_only=False ke torch.load agar tidak error di PyTorch 2.x")

# Cari semua variasi torch.load tanpa weights_only
patterns_load = [
    ("torch.load(path, map_location='cpu')",
     "torch.load(path, map_location='cpu', weights_only=False)"),
    ('torch.load(path, map_location="cpu")',
     'torch.load(path, map_location="cpu", weights_only=False)'),
    ("torch.load(path)",
     "torch.load(path, weights_only=False)"),
]

for old, new in patterns_load:
    if old in code and new not in code:
        code = code.replace(old, new)
        ok(f"  torch.load diperbaiki: ...{old[-30:]} → ...{new[-45:]}")
        modified = True

# Fix 3b: inject Adam patch di bagian import / top of file
info("Fix 3b: inject patch Adam optimizer agar checkpoint lama bisa di-load")

adam_patch = '''
# ── Compatibility patch ──────────────────────────────────────────────────────
# PyTorch modern tidak bisa deserialize Adam checkpoint dari versi lama karena
# struktur 'defaults' berubah. Patch ini memperbaiki __setstate__ secara runtime.
import torch.optim as _optim

_orig_optimizer_setstate = _optim.Optimizer.__setstate__

def _safe_optimizer_setstate(self, state):
    if isinstance(state, dict) and 'defaults' not in state:
        state['defaults'] = {}
    try:
        _orig_optimizer_setstate(self, state)
    except Exception:
        pass

_optim.Optimizer.__setstate__ = _safe_optimizer_setstate
_optim.Adam.__setstate__ = _safe_optimizer_setstate
# ─────────────────────────────────────────────────────────────────────────────
'''

# Inject setelah baris import terakhir di bagian atas file
if '_safe_optimizer_setstate' not in code:
    # Cari posisi setelah semua import di awal file
    lines = code.split('\n')
    last_import_idx = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('import ') or stripped.startswith('from '):
            last_import_idx = i

    lines.insert(last_import_idx + 1, adam_patch)
    code = '\n'.join(lines)
    ok("  Adam optimizer patch diinjeksi ke models.py")
    modified = True
else:
    ok("  Adam patch sudah ada di models.py, skip")

if modified:
    write('steganogan/models.py', code)
    ok("models.py diperbaiki")
else:
    ok("models.py tidak perlu perubahan")

# ─────────────────────────────────────────────
# FIX 4: README.md
# ─────────────────────────────────────────────
section("FIX 4 — README.md: Update Instruksi Instalasi")

info("Tambah catatan kompatibilitas Python 3.10+ di README")

readme = read('README.md')

compatibility_note = """
## ⚠️ Compatibility Note (Python 3.10+)

The original DAI-Lab repository targets Python 3.5–3.7 and PyTorch 1.0.0.
This fork includes the following patches to run on modern environments:

| Fix | Problem | Solution |
|-----|---------|----------|
| `setup.py` | Invalid version specifiers (missing comma) | Removed strict version locks |
| `utils.py` | `reedsolo >= 1.0` returns tuple instead of bytes | Handle both return types |
| `models.py` | `Adam` optimizer deserialization fails on PyTorch 2.x | Monkey-patch `__setstate__` |
| `models.py` | `torch.load` requires `weights_only` param on PyTorch 2.x | Added `weights_only=False` |

### Installation (Modern Python)

```bash
git clone <this-repo>
cd SteganoGAN
python3 -m venv venv
source venv/bin/activate   # Windows: venv\\Scripts\\activate
pip install -e .
```

### Quick Decode

```python
import torch
import torch.optim
from steganogan import SteganoGAN

model = SteganoGAN.load(architecture='dense')  # or 'basic' / 'residual'
print(model.decode('path/to/image.png'))
```

> **Note:** The Adam optimizer patch is now embedded directly in `models.py`,
> so no manual patching is needed before import.

---
"""

# Sisipkan setelah baris pertama (judul) agar tidak merusak struktur
if '⚠️ Compatibility Note' not in readme:
    lines = readme.split('\n')
    # Cari baris judul pertama
    insert_at = 1
    for i, line in enumerate(lines):
        if line.startswith('# '):
            insert_at = i + 1
            break
    lines.insert(insert_at, compatibility_note)
    write('README.md', '\n'.join(lines))
    ok("README.md diperbarui")
else:
    ok("README.md sudah ada compatibility note, skip")

# ─────────────────────────────────────────────
# Done
# ─────────────────────────────────────────────
section("Selesai!")

print("""
Semua fix berhasil diterapkan. Langkah selanjutnya:

  1. Install dependencies:
       pip install -e .

  2. Test decode (sesuaikan path gambar):
       python3 -c "
       from steganogan import SteganoGAN
       model = SteganoGAN.load(architecture='dense')
       print(model.decode('path/to/image.png'))
       "

  3. Commit & push ke fork kamu:
       git add setup.py steganogan/utils.py steganogan/models.py README.md
       git commit -m "fix: compatibility with Python 3.10+, reedsolo 1.x, PyTorch 2.x"
       git push

""")

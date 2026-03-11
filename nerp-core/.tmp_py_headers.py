#!/usr/bin/env python3
"""Add NERP ownership headers to all .py files (excluding venv/third-party)."""
import os

ROOT = '/Users/emmanuelnaweji/Naweji-Reliability-Platform'
SKIP_DIRS = {'.git', '.venv', 'node_modules', '__pycache__'}

PY_HEADER = '''# ===========================================================================
# NERP - Naweji Enterprise Reliability Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/Naweji-Reliability-Platform
# ===========================================================================
'''

def get_files(root, extensions):
    result = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            if any(f.endswith(ext) for ext in extensions):
                fp = os.path.join(dirpath, f)
                if '/ai/.venv/' not in fp and '/node_modules/' not in fp:
                    result.append(fp)
    return sorted(result)

py_files = get_files(ROOT, ['.py'])
modified = 0

for fpath in py_files:
    # Skip temp files
    if '.tmp_' in fpath:
        continue
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        continue

    if 'NERP - Naweji Enterprise Reliability Platform' in content:
        continue

    # Check for shebang or encoding declaration at top
    lines = content.split('\n')
    insert_after = 0
    
    if lines and (lines[0].startswith('#!') or lines[0].startswith('# -*-')):
        insert_after = 1
        if len(lines) > 1 and lines[1].startswith('# -*-'):
            insert_after = 2

    before = '\n'.join(lines[:insert_after])
    after = '\n'.join(lines[insert_after:])
    
    if before:
        new_content = before + '\n' + PY_HEADER + after
    else:
        new_content = PY_HEADER + after

    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    rel = os.path.relpath(fpath, ROOT)
    print(f'  [PY] {rel}')
    modified += 1

print(f'\nTotal: {modified} .py files updated with NERP ownership')

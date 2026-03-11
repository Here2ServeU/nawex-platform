#!/usr/bin/env python3
"""Add NERP ownership headers to all .sh files and footers to all .md files."""
import os
import re

ROOT = '/Users/emmanuelnaweji/Naweji-Reliability-Platform'
SKIP_DIRS = {'.git', '.venv', 'node_modules', '__pycache__'}

SH_HEADER = """# ===========================================================================
# NERP - Naweji Enterprise Reliability Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/Naweji-Reliability-Platform
# ===========================================================================
"""

MD_FOOTER = """
---

*Copyright (c) 2026 Naweji Enterprise Reliability Platform (NERP). Owned by Rev. Dr. Emmanuel Naweji. All rights reserved.*
"""

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

# --- Process .sh files ---
sh_files = get_files(ROOT, ['.sh'])
sh_modified = 0

for fpath in sh_files:
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        continue

    # Skip if already has NERP header
    if 'NERP - Naweji Enterprise Reliability Platform' in content:
        continue

    lines = content.split('\n')
    
    # Find the shebang line
    if lines and lines[0].startswith('#!'):
        shebang = '#!/usr/bin/env bash'  # Standardize shebang
        rest = '\n'.join(lines[1:])
        # Strip any blank lines right after shebang
        rest = rest.lstrip('\n')
        new_content = shebang + '\n' + SH_HEADER + rest
    else:
        new_content = '#!/usr/bin/env bash\n' + SH_HEADER + content

    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    rel = os.path.relpath(fpath, ROOT)
    print(f'  [SH] {rel}')
    sh_modified += 1

# --- Process .md files ---
md_files = get_files(ROOT, ['.md'])
md_modified = 0

for fpath in md_files:
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        continue

    # Skip if already has NERP copyright footer
    if 'Copyright (c) 2026 Naweji Enterprise Reliability Platform' in content:
        continue

    # Strip trailing whitespace/newlines
    content = content.rstrip()
    
    # Add footer
    content = content + '\n' + MD_FOOTER

    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(content)
    rel = os.path.relpath(fpath, ROOT)
    print(f'  [MD] {rel}')
    md_modified += 1

print(f'\nTotal: {sh_modified} .sh files + {md_modified} .md files updated with NERP ownership')

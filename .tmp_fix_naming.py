#!/usr/bin/env python3
"""Fix script quality issues: old naming, duplicates, author references."""
import os
import re

ROOT = '/Users/emmanuelnaweji/Naweji-Reliability-Platform'

# 1. Fix old naming in ALL .sh files
old_to_new = [
    ('Express-Reliability AIOps Platform', 'Naweji Reliability Platform (NRP)'),
    ('Express-Reliability AIOps', 'Naweji Reliability Platform (NRP)'),
    ('Express Reliability AIOps Platform', 'Naweji Reliability Platform (NRP)'),
    ('Express Reliability AIOps', 'Naweji Reliability Platform (NRP)'),
    ('Express Reliability Platform', 'Naweji Reliability Platform (NRP)'),
    ('Express-Reliability: Fintech', 'NRP: Fintech'),
    ('Express-Reliability: Healthcare', 'NRP: Healthcare'),
    ('Express Reliability', 'Naweji Reliability Platform'),
    ('express-reliability-aiops-platform', 'Naweji-Reliability-Platform'),
    ('Express-Reliability AIOps DevSecOps', 'NRP DevSecOps'),
    ('Bootstrapping Express Reliability AIOps Platform', 'Bootstrapping Naweji Reliability Platform (NRP)'),
    ('express-t2s.com', 'nrp-platform.com'),
]

# 2. Fix author references in .md files
author_replacements = [
    ('Emmanuel Naweji, Ph.D. Candidate (AI/ML)', 'Rev. Dr. Emmanuel Naweji'),
    ('Naweji Development Team', 'Rev. Dr. Emmanuel Naweji'),
]

SKIP_DIRS = {'.git', '.venv', 'node_modules', '__pycache__'}

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

# Process .sh files for old naming
sh_files = get_files(ROOT, ['.sh'])
sh_fixed = 0

for fpath in sh_files:
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        continue
    
    original = content
    for old, new in old_to_new:
        content = content.replace(old, new)
    
    if content != original:
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(content)
        rel = os.path.relpath(fpath, ROOT)
        print(f'  [SH naming] {rel}')
        sh_fixed += 1

# Process .md files for author references
md_files = get_files(ROOT, ['.md'])
md_fixed = 0

for fpath in md_files:
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        continue
    
    original = content
    for old, new in author_replacements:
        content = content.replace(old, new)
    
    # Also fix old naming in .md (catch any remainders from scripts)
    for old, new in old_to_new:
        content = content.replace(old, new)
    
    if content != original:
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(content)
        rel = os.path.relpath(fpath, ROOT)
        print(f'  [MD fix] {rel}')
        md_fixed += 1

print(f'\nTotal: {sh_fixed} .sh + {md_fixed} .md files fixed (naming/author)')

#!/usr/bin/env python3
"""Remove emojis from all project .md, .sh, and .py files."""
import os
import re

ROOT = '/Users/emmanuelnaweji/Naweji-Reliability-Platform'

# Comprehensive emoji regex
emoji_pattern = re.compile(
    '['
    '\U0001F300-\U0001FAFF'
    '\U00002600-\U000027BF'
    '\U0000FE00-\U0000FE0F'
    '\U0000200D'
    '\U00002B50-\U00002B55'
    '\U0000231A-\U000023F3'
    '\U00002934-\U00002935'
    '\U000025AA-\U000025FE'
    '\U00002B1B-\U00002B1C'
    '\U0000203C'
    '\U00002049'
    '\U00002702-\U000027B0'
    '\U00002122'
    '\U00002139'
    '\U00002194-\U000021AA'
    '\U000023CE-\U000023CF'
    '\U000023E9-\U000023F3'
    '\U000023F8-\U000023FA'
    '\U000025B6'
    '\U000025C0'
    '\U00002611'
    '\U00002714'
    '\U00002716'
    '\U00002728'
    '\U00002733-\U00002734'
    '\U0000274C'
    '\U0000274E'
    '\U00002753-\U00002757'
    '\U00002763-\U00002764'
    '\U00010000-\U0010FFFF'
    ']+', re.UNICODE
)

specific_chars = [
    '\u25BC', '\u25B2', '\u2714', '\u2718', '\u2713',
    '\u2717', '\u2716', '\u274C', '\u2B50', '\u26A0',
    '\u25B6', '\u279C', '\u231B', '\u2705',
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

files = get_files(ROOT, ['.md', '.sh', '.py'])
total_modified = 0

for fpath in files:
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        continue

    original = content

    # Remove specific chars first
    for ch in specific_chars:
        content = content.replace(ch, '')

    # Remove emoji ranges
    content = emoji_pattern.sub('', content)

    # Clean up double/triple spaces that result (but preserve indentation)
    lines = content.split('\n')
    cleaned_lines = []
    for line in lines:
        # Preserve leading whitespace, clean mid-line double spaces
        stripped = line.lstrip()
        indent = line[:len(line) - len(stripped)]
        stripped = re.sub(r' +', ' ', stripped)
        # Remove leading space if emoji was at line start and left a space
        stripped = stripped.lstrip(' ') if stripped.startswith(' ') and not indent else stripped
        cleaned_lines.append(indent + stripped)
    content = '\n'.join(cleaned_lines)

    if content != original:
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(content)
        rel = os.path.relpath(fpath, ROOT)
        print(f' Fixed: {rel}')
        total_modified += 1

print(f'\nTotal: {total_modified} files cleaned of emojis')

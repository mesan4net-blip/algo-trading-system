#!/usr/bin/env python3
"""
Pine Script v6 Validator + GitHub Push Tool
Usage: python3 validate_pine.py <file.pine> [--push]

Checks for common Pine Script v6 errors before pushing:
  1. Unmatched parentheses
  2. Variables used before declaration
  3. Bare if/else blocks with no body
  4. Stale indented assignments outside any block
  5. Multiline string concatenation (CE10156)
  6. Duplicate var declarations
"""

import sys
import re
import json
import base64
import subprocess
import os

# ── Config ────────────────────────────────────────────────────────────────────
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO         = "mesan4net-blip/algo-trading-system"
BRANCH       = "main"

# Variables that must be declared before use
# Format: (declaration_pattern, variable_name)
CRITICAL_VARS = [
    (r'^var string active_dir',      'active_dir'),
    (r'^var float\s+active_sl',      'active_sl'),
    (r'^var float\s+last_active_sl', 'last_active_sl'),
    (r'^var string trail_dir',       'trail_dir'),
    (r'^var float tsl_long_val',     'tsl_long_val'),
    (r'^var float tsl_short_val',    'tsl_short_val'),
    (r'^var float\[\].*trade_sl_levels', 'trade_sl_levels'),
    (r'^var string\[\].*trade_sl_dirs',  'trade_sl_dirs'),
    (r'^var float\[\].*trade_entry_prices', 'trade_entry_prices'),
    (r'^var int\[\].*trade_entry_times',    'trade_entry_times'),
    (r'^atr14\s*=',                  'atr14'),
    (r'^f_sz\s*\(',                  'f_sz'),
    (r'^f_dot_sz\s*\(',              'f_dot_sz'),
    (r'^f_show_bull\s*\(',           'f_show_bull'),
    (r'^f_show_bear\s*\(',           'f_show_bear'),
    (r'^sl_long_preview\s*=',        'sl_long_preview'),
    (r'^sl_short_preview\s*=',       'sl_short_preview'),
    (r'^tsl_long_raw\s*=',           'tsl_long_raw'),
    (r'^tsl_short_raw\s*=',          'tsl_short_raw'),
    (r'^no_new_trade\s*=',           'no_new_trade'),
    (r'^is_any_active\s*=',          'is_any_active'),
    (r'^any_bull_signal\s*=',        'any_bull_signal'),
    (r'^any_bear_signal\s*=',        'any_bear_signal'),
    (r'^in_date_range\s*=',          'in_date_range'),
    (r'^pyramiding_allowed\s*=',     'pyramiding_allowed'),
    (r'^enable_tsl\s*=',             'enable_tsl'),
]

errors   = []
warnings = []

def check(filepath):
    with open(filepath) as f:
        content = f.read()
    lines = content.split('\n')

    # 1. Unmatched parentheses
    opens  = content.count('(')
    closes = content.count(')')
    if opens != closes:
        errors.append(f"UNMATCHED PARENS: {opens} '(' vs {closes} ')' — diff = {opens - closes}")

    # 2. Stale indented assignments (e.g. "        tsl_short_val := na" at top level)
    for i, line in enumerate(lines, 1):
        stripped = line.lstrip()
        indent   = len(line) - len(stripped)
        # Assignment with := at top-level indentation (inside no block)
        if indent >= 8 and ':=' in stripped and not stripped.startswith('//'):
            # Check if previous non-blank line ends a block context
            # Simple heuristic: if indented more than 4 and not inside if/for/while
            context_lines = [l for l in lines[max(0,i-5):i-1] if l.strip()]
            if context_lines:
                last = context_lines[-1].strip()
                if not any(last.startswith(kw) for kw in ['if ', 'else', 'for ', 'while ', 'if(', 'else{', '//']):
                    warnings.append(f"Line {i}: Possibly stale indented assignment: {line.rstrip()[:70]}")

    # 3. Empty if/else blocks (CE10144)
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped in ('else', 'else:') and i < len(lines):
            next_lines = [l for l in lines[i:i+3] if l.strip() and not l.strip().startswith('//')]
            if next_lines:
                next_stripped = next_lines[0].strip()
                # If next non-blank line is at same or lower indent level, empty else body
                curr_indent = len(line) - len(line.lstrip())
                next_indent = len(lines[i]) - len(lines[i].lstrip()) if i < len(lines) else 0
                if next_indent <= curr_indent and not next_stripped.startswith('if '):
                    errors.append(f"Line {i}: Empty else block (CE10144) — no body after 'else'")

    # 4. Declaration order — check each critical var
    for pattern, varname in CRITICAL_VARS:
        decl_line = None
        for i, line in enumerate(lines, 1):
            if re.match(pattern, line.strip()):
                decl_line = i
                break

        if decl_line is None:
            errors.append(f"MISSING DECLARATION: '{varname}' is used but never declared")
            continue

        # Find first use (excluding the declaration line itself)
        use_pattern = re.compile(r'\b' + re.escape(varname) + r'\b')
        for i, line in enumerate(lines, 1):
            if i == decl_line:
                continue
            if use_pattern.search(line) and not line.strip().startswith('//'):
                if i < decl_line:
                    errors.append(f"USE BEFORE DECLARATION: '{varname}' used at line {i} but declared at line {decl_line}")
                break

    # 5. Duplicate var declarations
    var_decls = {}
    for i, line in enumerate(lines, 1):
        m = re.match(r'\s*var\s+\w+[\[\]]*\s+(\w+)\s*=', line)
        if m:
            name = m.group(1)
            if name in var_decls:
                errors.append(f"DUPLICATE DECLARATION: '{name}' declared at lines {var_decls[name]} and {i}")
            else:
                var_decls[name] = i

    # 6. Multiline string concatenation (CE10156)
    for i, line in enumerate(lines, 1):
        stripped = line.rstrip()
        if stripped.endswith('+') or stripped.endswith('?') or stripped.endswith(':'):
            if not stripped.strip().startswith('//'):
                warnings.append(f"Line {i}: Possible multiline expression (CE10156): {stripped[:70]}")

    return len(errors) == 0

def remote_path(filepath):
    """Mirror the local repo layout: use the path from 'phase1/' onward so a
    file in phase1/strategies/ pushes to phase1/strategies/, one in
    phase1/legacy/ to phase1/legacy/, etc. Falls back to phase1/strategies/
    (where new per-entry scripts live) when the path isn't under phase1/."""
    parts = filepath.replace(os.sep, '/').split('/')
    if 'phase1' in parts:
        return '/'.join(parts[parts.index('phase1'):])
    return f"phase1/strategies/{os.path.basename(filepath)}"


def push(filepath, commit_msg):
    import urllib.request, urllib.error
    with open(filepath, 'rb') as f:
        content_b64 = base64.b64encode(f.read()).decode()

    dest = remote_path(filepath)
    url  = f"https://api.github.com/repos/{REPO}/contents/{dest}"
    print(f"→ target: {dest}")

    # Get current file SHA if the file already exists (needed to UPDATE).
    # A 404 just means it's a new file — push it without a sha to CREATE it.
    file_sha = None
    getreq = urllib.request.Request(url, headers={"Authorization": f"token {GITHUB_TOKEN}"})
    try:
        with urllib.request.urlopen(getreq) as r:
            file_sha = json.load(r)['sha']
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise

    # Push (create or update)
    payload_obj = {
        'message': commit_msg,
        'content': content_b64,
        'branch':  BRANCH
    }
    if file_sha:
        payload_obj['sha'] = file_sha
    payload = json.dumps(payload_obj).encode()

    req = urllib.request.Request(url, data=payload, method='PUT', headers={
        "Authorization": f"token {GITHUB_TOKEN}",
        "Content-Type":  "application/json"
    })
    with urllib.request.urlopen(req) as r:
        result = json.load(r)
    return result['commit']['sha'][:10]


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 validate_pine.py <file.pine> [--push 'commit message']")
        sys.exit(1)

    filepath = sys.argv[1]
    do_push  = '--push' in sys.argv

    print(f"\n{'='*60}")
    print(f"Validating: {filepath}")
    print(f"{'='*60}")

    clean = check(filepath)

    if errors:
        print(f"\n❌ ERRORS ({len(errors)}):")
        for e in errors:
            print(f"  • {e}")

    if warnings:
        print(f"\n⚠️  WARNINGS ({len(warnings)}):")
        for w in warnings:
            print(f"  • {w}")

    if clean:
        print(f"\n✅ No errors found — file looks clean")
        if do_push:
            idx = sys.argv.index('--push')
            msg = sys.argv[idx+1] if idx+1 < len(sys.argv) else f"Update {os.path.basename(filepath)}"
            commit = push(filepath, msg)
            print(f"✅ Pushed — commit {commit}")
    else:
        print(f"\n🚫 NOT pushing — fix errors first")
        sys.exit(1)

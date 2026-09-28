#!/usr/bin/env python3
"""Package-level checks that do not require Django to be imported."""
import ast
import py_compile
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
errors = []

for path in list((ROOT / 'asset_mgmt').rglob('*.py')) + list((ROOT / 'chem_asset_mvp').rglob('*.py')) + [ROOT / 'manage.py']:
    try:
        py_compile.compile(str(path), doraise=True)
    except py_compile.PyCompileError as exc:
        errors.append(str(exc))

views_tree = ast.parse((ROOT / 'asset_mgmt/views.py').read_text(encoding='utf-8'))
view_defs = {node.name for node in views_tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))}
urls_text = (ROOT / 'asset_mgmt/urls.py').read_text(encoding='utf-8')
view_refs = set(re.findall(r'views\.([A-Za-z_][A-Za-z0-9_]*)', urls_text))
for name in sorted(view_refs - view_defs):
    errors.append(f'URL references missing view: {name}')

url_names = set(re.findall(r"name=['\"]([^'\"]+)", urls_text))
url_names |= set(re.findall(r"name=['\"]([^'\"]+)", (ROOT / 'chem_asset_mvp/urls.py').read_text(encoding='utf-8')))
for path in (ROOT / 'asset_mgmt/templates').rglob('*.html'):
    text = path.read_text(encoding='utf-8')
    for name in re.findall(r"{%\s*url\s+['\"]([^'\"]+)", text):
        if name not in url_names:
            errors.append(f'{path.relative_to(ROOT)} references missing URL name: {name}')
    for opening, closing in [('if', 'endif'), ('for', 'endfor'), ('block', 'endblock'), ('with', 'endwith')]:
        open_count = len(re.findall(r'{%\s*' + opening + r'\b', text))
        close_count = len(re.findall(r'{%\s*' + closing + r'\s*%}', text))
        if open_count != close_count:
            errors.append(f'{path.relative_to(ROOT)} unbalanced {opening}/{closing}: {open_count}/{close_count}')

roles_tree = ast.parse((ROOT / 'asset_mgmt/roles.py').read_text(encoding='utf-8'))
role_keys = set()
for node in roles_tree.body:
    if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'ROLE_URL_ACCESS' for target in node.targets):
        role_keys = {key.value for key in node.value.keys if isinstance(key, ast.Constant)}
for name in sorted(set(re.findall(r"name=['\"]([^'\"]+)", urls_text)) - role_keys):
    errors.append(f'URL has no explicit role mapping: {name}')
for name in sorted(role_keys - set(re.findall(r"name=['\"]([^'\"]+)", urls_text))):
    errors.append(f'Role mapping has no URL: {name}')

if errors:
    print('STATIC VALIDATION FAILED')
    for error in errors:
        print(f'- {error}')
    sys.exit(1)
print('STATIC VALIDATION PASSED')

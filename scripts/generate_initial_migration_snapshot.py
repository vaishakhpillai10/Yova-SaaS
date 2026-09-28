#!/usr/bin/env python3
"""Generate a versioned initial migration from the current models.py without importing Django.

This exists so release packaging is deterministic even in restricted build environments.
The generated migration uses normal Django migration operations and must still be executed
and verified with `python manage.py migrate` in a Django-enabled environment.
"""
from __future__ import annotations
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'asset_mgmt' / 'models.py'
OUT = ROOT / 'asset_mgmt' / 'migrations' / '0001_initial.py'
source = SRC.read_text(encoding='utf-8')
tree = ast.parse(source)

model_classes = {}
class_constants = {}
for node in tree.body:
    if not isinstance(node, ast.ClassDef):
        continue
    is_model = any(
        (isinstance(base, ast.Name) and base.id == 'TimeStampedModel') or
        (isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name) and base.value.id == 'models' and base.attr == 'Model')
        for base in node.bases
    )
    if is_model and node.name != 'TimeStampedModel':
        model_classes[node.name] = node
    consts = {}
    for stmt in node.body:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            name = stmt.targets[0].id
            if not (isinstance(stmt.value, ast.Call) and isinstance(stmt.value.func, ast.Attribute) and isinstance(stmt.value.func.value, ast.Name) and stmt.value.func.value.id == 'models'):
                consts[name] = stmt.value
    class_constants[node.name] = consts

GLOBAL_CONSTS = {}
for stmt in tree.body:
    if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
        GLOBAL_CONSTS[stmt.targets[0].id] = stmt.value

class FieldTransformer(ast.NodeTransformer):
    def __init__(self, owner):
        self.owner = owner

    def visit_Name(self, node):
        if node.id in class_constants.get(self.owner, {}):
            return ast.copy_location(ast.fix_missing_locations(ast.parse(ast.unparse(class_constants[self.owner][node.id]), mode='eval').body), node)
        if node.id in GLOBAL_CONSTS and node.id not in {'POSITIVE_DECIMAL','NON_NEGATIVE_DECIMAL','DOCUMENT_VALIDATORS','IMAGE_VALIDATORS'}:
            return ast.copy_location(ast.fix_missing_locations(ast.parse(ast.unparse(GLOBAL_CONSTS[node.id]), mode='eval').body), node)
        return node

    def visit_Attribute(self, node):
        # Literalize class-level choice constants such as Asset.CONDITION_CHOICES.
        if isinstance(node.value, ast.Name):
            const = class_constants.get(node.value.id, {}).get(node.attr)
            if const is not None:
                return ast.copy_location(ast.fix_missing_locations(ast.parse(ast.unparse(const), mode='eval').body), node)
        return self.generic_visit(node)

    def visit_Call(self, node):
        node = self.generic_visit(node)
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == 'models' and node.func.attr in {'ForeignKey','OneToOneField','ManyToManyField'} and node.args:
            target = node.args[0]
            if isinstance(target, ast.Name) and target.id in model_classes:
                node.args[0] = ast.Constant(f'asset_mgmt.{target.id.lower()}')
            elif isinstance(target, ast.Constant) and isinstance(target.value, str):
                if target.value != 'self' and target.value in model_classes:
                    node.args[0] = ast.Constant(f'asset_mgmt.{target.value.lower()}')
        return node


def transformed_expr(expr, owner):
    copy = ast.parse(ast.unparse(expr), mode='eval').body
    copy = FieldTransformer(owner).visit(copy)
    ast.fix_missing_locations(copy)
    return ast.unparse(copy)


def is_field_expr(expr):
    if not (isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute) and isinstance(expr.func.value, ast.Name) and expr.func.value.id == 'models'):
        return False
    return expr.func.attr.endswith('Field') or expr.func.attr in {'ForeignKey', 'OneToOneField', 'ManyToManyField'}


def local_relation_dependencies(owner, cls):
    deps = set()
    for stmt in cls.body:
        value = None
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            value = stmt.value
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            value = stmt.value
        if not isinstance(value, ast.Call):
            continue
        func = value.func
        if not (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == 'models' and func.attr in {'ForeignKey', 'OneToOneField', 'ManyToManyField'}):
            continue
        if not value.args:
            continue
        target = value.args[0]
        target_name = None
        if isinstance(target, ast.Name) and target.id in model_classes:
            target_name = target.id
        elif isinstance(target, ast.Constant) and isinstance(target.value, str) and target.value in model_classes:
            target_name = target.value
        if target_name and target_name != owner:
            deps.add(target_name)
    return deps


# Create referenced local models before models that own their foreign keys. The source file
# intentionally contains a few forward relations (for example PMCall -> WorkOrder and
# WorkOrderSpare -> PurchaseRequest); topological ordering keeps this hand-off migration
# executable on a fresh database without relying on unresolved future tables.
dependencies = {name: local_relation_dependencies(name, cls) for name, cls in model_classes.items()}
remaining = list(model_classes)
ordered_model_names = []
created = set()
while remaining:
    ready = [name for name in remaining if dependencies[name] <= created]
    if not ready:
        unresolved = {name: sorted(dependencies[name] - created) for name in remaining}
        raise RuntimeError(f'Local model dependency cycle detected: {unresolved}')
    # Preserve source order among models that are ready.
    for name in ready:
        ordered_model_names.append(name)
        created.add(name)
        remaining.remove(name)

ops = []
for name in ordered_model_names:
    cls = model_classes[name]
    inherits_ts = any(isinstance(base, ast.Name) and base.id == 'TimeStampedModel' for base in cls.bases)
    fields = [("id", "models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')")]
    if inherits_ts:
        fields += [
            ('created_at', 'models.DateTimeField(auto_now_add=True)'),
            ('updated_at', 'models.DateTimeField(auto_now=True)'),
        ]
    for stmt in cls.body:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name) and is_field_expr(stmt.value):
            fields.append((stmt.targets[0].id, transformed_expr(stmt.value, name)))
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.value is not None and is_field_expr(stmt.value):
            fields.append((stmt.target.id, transformed_expr(stmt.value, name)))

    options = []
    meta = next((x for x in cls.body if isinstance(x, ast.ClassDef) and x.name == 'Meta'), None)
    if meta:
        for stmt in meta.body:
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                key = stmt.targets[0].id
                if key in {'ordering','verbose_name','verbose_name_plural','constraints','indexes','permissions','db_table'}:
                    options.append((key, transformed_expr(stmt.value, name)))

    field_lines = ',\n                '.join(f"({field_name!r}, {field_expr})" for field_name, field_expr in fields)
    option_lines = ',\n                '.join(f"{key!r}: {expr}" for key, expr in options)
    op = f"""migrations.CreateModel(\n            name={name!r},\n            fields=[\n                {field_lines}\n            ],\n            options={{\n                {option_lines}\n            }},\n        )"""
    ops.append(op)

content = f'''# Generated by scripts/generate_initial_migration_snapshot.py on 2026-08-08.\n# This is a version-controlled schema snapshot for the remediated CMMS release.\nfrom decimal import Decimal\n\nfrom django.conf import settings\nfrom django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator\nfrom django.db import migrations, models\nfrom django.db.models import Q\nfrom django.utils import timezone\n\nPOSITIVE_DECIMAL = [MinValueValidator(Decimal("0.01"))]\nNON_NEGATIVE_DECIMAL = [MinValueValidator(Decimal("0.00"))]\nDOCUMENT_VALIDATORS = [FileExtensionValidator(["pdf", "doc", "docx", "xls", "xlsx", "csv", "jpg", "jpeg", "png"])]\nIMAGE_VALIDATORS = [FileExtensionValidator(["jpg", "jpeg", "png", "webp"])]\n\n\nclass Migration(migrations.Migration):\n    initial = True\n    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]\n    operations = [\n        {',\n        '.join(ops)}\n    ]\n'''
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(content, encoding='utf-8')
print(f'Wrote {OUT.relative_to(ROOT)} with {len(ops)} CreateModel operations')

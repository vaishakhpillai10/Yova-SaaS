#!/usr/bin/env python3
"""Static release gate for the QA-remediated CMMS.

This does not replace `manage.py check` or `manage.py test`. It makes the specific
regressions discovered during the 2026-08-08 QA audit fail the build even in a
restricted environment where Django cannot be imported.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILURES: list[str] = []
PASSES: list[str] = []


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASSES.append(name)
        print(f"PASS  {name}")
    else:
        FAILURES.append(f"{name}: {detail}" if detail else name)
        print(f"FAIL  {name}" + (f" -- {detail}" if detail else ""))


def class_source(path: str, class_name: str) -> str:
    src = read(path)
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return ast.get_source_segment(src, node) or ""
    return ""


def function_source(path: str, function_name: str) -> str:
    src = read(path)
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            return ast.get_source_segment(src, node) or ""
    return ""


def source_model_fields() -> dict[str, set[str]]:
    src = read("asset_mgmt/models.py")
    tree = ast.parse(src)
    result: dict[str, set[str]] = {}
    relation_names = {"ForeignKey", "OneToOneField", "ManyToManyField"}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        is_ts = any(isinstance(b, ast.Name) and b.id == "TimeStampedModel" for b in node.bases)
        is_model = is_ts or any(
            isinstance(b, ast.Attribute)
            and isinstance(b.value, ast.Name)
            and b.value.id == "models"
            and b.attr == "Model"
            for b in node.bases
        )
        if not is_model or node.name == "TimeStampedModel":
            continue
        fields = {"id"}
        if is_ts:
            fields |= {"created_at", "updated_at"}
        for stmt in node.body:
            target = value = None
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                target, value = stmt.targets[0].id, stmt.value
            elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                target, value = stmt.target.id, stmt.value
            if not target or not isinstance(value, ast.Call):
                continue
            f = value.func
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "models":
                if f.attr.endswith("Field") or f.attr in relation_names:
                    fields.add(target)
        result[node.name.lower()] = fields
    return result


def migration_fields() -> dict[str, set[str]]:
    src = read("asset_mgmt/migrations/0001_initial.py")
    tree = ast.parse(src)
    result: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if not (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "migrations" and f.attr == "CreateModel"):
            continue
        kwargs = {kw.arg: kw.value for kw in node.keywords if kw.arg}
        name_node = kwargs.get("name")
        fields_node = kwargs.get("fields")
        if not (isinstance(name_node, ast.Constant) and isinstance(name_node.value, str) and isinstance(fields_node, ast.List)):
            continue
        fields: set[str] = set()
        for elt in fields_node.elts:
            if isinstance(elt, ast.Tuple) and elt.elts and isinstance(elt.elts[0], ast.Constant):
                fields.add(str(elt.elts[0].value))
        result[name_node.value.lower()] = fields
    return result


# 1. Package schema/migration integrity.
mig = ROOT / "asset_mgmt/migrations/0001_initial.py"
check("QA-24 Versioned migration exists", mig.exists(), "0001_initial.py missing")
if mig.exists():
    src_fields = source_model_fields()
    mig_fields = migration_fields()
    missing_models = sorted(set(src_fields) - set(mig_fields))
    extra_models = sorted(set(mig_fields) - set(src_fields))
    field_mismatches = {
        model: (sorted(src_fields[model] - mig_fields.get(model, set())), sorted(mig_fields.get(model, set()) - src_fields[model]))
        for model in src_fields
        if src_fields[model] != mig_fields.get(model, set())
    }
    check(
        "Migration model/field snapshot matches models.py",
        not missing_models and not extra_models and not field_mismatches,
        f"missing_models={missing_models}, extra_models={extra_models}, field_mismatches={field_mismatches}",
    )

# 2. CSRF on every template POST form.
csrf_missing: list[str] = []
form_re = re.compile(r"<form\b[^>]*\bmethod\s*=\s*['\"]post['\"][^>]*>(.*?)</form>", re.I | re.S)
for tpl in (ROOT / "asset_mgmt/templates").rglob("*.html"):
    text = tpl.read_text(encoding="utf-8")
    for idx, body in enumerate(form_re.findall(text), start=1):
        if "{% csrf_token %}" not in body:
            csrf_missing.append(f"{tpl.relative_to(ROOT)} form#{idx}")
check("QA-04 All POST forms have CSRF tokens", not csrf_missing, ", ".join(csrf_missing))

# 3. No internet dependency for core UI.
external_refs: list[str] = []
external_pattern = re.compile(r"(?:src|href)\s*=\s*['\"]https?://", re.I)
for p in list((ROOT / "asset_mgmt/templates").rglob("*.html")) + list((ROOT / "asset_mgmt/static").rglob("*")):
    if p.is_file():
        try:
            if external_pattern.search(p.read_text(encoding="utf-8")):
                external_refs.append(str(p.relative_to(ROOT)))
        except UnicodeDecodeError:
            pass
check("QA-26 Core UI has no external CDN dependency", not external_refs, ", ".join(external_refs))

forms = read("asset_mgmt/forms.py")
models = read("asset_mgmt/models.py")
views = read("asset_mgmt/views.py")
workflow = read("asset_mgmt/services/maintenance_workflow.py")
sap_pm = read("asset_mgmt/services/sap_pm.py")
inv = read("asset_mgmt/services/inventory.py")
reliability = read("asset_mgmt/services/reliability.py")
pm_service = read("asset_mgmt/services/pm.py")
urls = read("asset_mgmt/urls.py")
roles = read("asset_mgmt/roles.py")
module_tpl = read("asset_mgmt/templates/asset_mgmt/module_list.html")

# 4. Source-of-truth forms / ledgers.
wo_form = class_source("asset_mgmt/forms.py", "WorkOrderForm")
spare_form = class_source("asset_mgmt/forms.py", "WorkOrderSpareForm")
po_form = class_source("asset_mgmt/forms.py", "PurchaseOrderForm")
invoice_form = class_source("asset_mgmt/forms.py", "VendorInvoiceForm")
check("WO status is not freely editable", "'status'" not in wo_form and '"status"' not in wo_form, "WorkOrderForm still exposes status")
check("QA-08 Material quantity_used is ledger-derived", "quantity_used" not in spare_form, "WorkOrderSpareForm exposes quantity_used")
check("QA-03 PO type/status are controlled actions", "'po_type'" not in po_form and "'status'" not in po_form and '"po_type"' not in po_form and '"status"' not in po_form, "PurchaseOrderForm exposes po_type/status")
check("Invoice clearance/payment are controlled actions", "accounts_clearance_status" not in invoice_form and "payment_status" not in invoice_form, "VendorInvoiceForm exposes controlled statuses")
check("Service PO type is derived before ModelForm model validation", "def clean(self):" in class_source("asset_mgmt/forms.py", "PurchaseOrderForm") and "self.instance.po_type" in class_source("asset_mgmt/forms.py", "PurchaseOrderForm"), "PO form does not derive system fields before model.clean()")
check("Goods receipt derives hidden plant/item before model validation", "self.instance.plant = po.plant" in class_source("asset_mgmt/forms.py", "GoodsReceiptForm") and "self.instance.item = po.item" in class_source("asset_mgmt/forms.py", "GoodsReceiptForm"), "GR form hidden fields are set too late")
check("Ambiguous multi-operation material issue is rejected", "planned on multiple operations" in class_source("asset_mgmt/models.py", "MaterialIssue") and "planned on multiple operations" in inv, "Operation is not required when same spare appears on multiple operations")

# 5. WO transition controls / edge paths.
for action in ["reject_approval", "return_planning", "return_execution", "cancel"]:
    check(f"QA-13 WO exception action {action} exists", f"'{action}'" in workflow, f"Missing {action}")
check("QA-14 WO creator cannot self-approve", "cannot approve their own work order" in workflow.lower(), "Self-approval guard missing")
check("WO technical lock enforced", "technical_lock" in workflow and "TECO work orders cannot be returned to execution" in workflow and "technical_lock" in views, "TECO lock guard missing")
check("Maintenance record-level WO control exists", "maintenance_user_can_control_work_order" in views and "assigned_to_id != request.user.id" in views, "Technician ownership enforcement missing")

# 6. Scheduling / operation dependencies.
cap_fn = function_source("asset_mgmt/services/sap_pm.py", "work_centre_capacity")
schedule_fn = function_source("asset_mgmt/services/sap_pm.py", "schedule_work_order")
confirmation = class_source("asset_mgmt/models.py", "WorkOrderConfirmation")
check("QA-07 Capacity uses persons_required labour-hours", "persons_required" in cap_fn and "planned_hours" in cap_fn and "default_crew_size" in cap_fn, "Capacity formula does not use crew/person requirements")
check("Technician double-booking blocked", "already scheduled" in schedule_fn and "assigned_to_id" in schedule_fn, "Schedule conflict guard missing")
check("QA-06 Predecessor enforced during scheduling", "predecessor" in schedule_fn and "cannot start before predecessor" in schedule_fn.lower(), "Scheduling predecessor guard missing")
check("QA-06 Predecessor enforced during confirmation", "predecessor" in confirmation and "must be completed" in confirmation.lower(), "Confirmation predecessor guard missing")
check("QA-06 Predecessor enforced during operation action", "predecessor" in views and "Complete predecessor operation" in views, "Execution predecessor guard missing")

# 7. Inventory/reservation/material issue.
check("QA-05 Transfers protect reserved stock", "reserved" in function_source("asset_mgmt/services/inventory.py", "post_stock_transfer") and "available" in function_source("asset_mgmt/services/inventory.py", "post_stock_transfer"), "Transfer does not subtract reservations")
issue_fn = function_source("asset_mgmt/services/inventory.py", "post_material_issue")
check("QA-09 Material issue is WO-lifecycle gated", "RELEASED" in issue_fn and "IN_PROGRESS" in issue_fn and "technical_lock" in issue_fn, "Material issue lifecycle guard missing")
check("Material over-issue is blocked", "planned" in issue_fn.lower() and ("remaining" in issue_fn.lower() or "exceeds" in issue_fn.lower()), "Planned quantity ceiling missing")
check("Material consumption updates reservation ledger", "quantity_used" in issue_fn and "InventoryReservation" in issue_fn, "Reservation/usage reconciliation missing")
gr_fn = function_source("asset_mgmt/services/inventory.py", "post_goods_receipt")
check("Received WO shortage stock becomes reserved", "InventoryReservation" in gr_fn and "work_order_spare" in gr_fn, "GR-to-WO reservation integration missing")
check("QA-01 TECO does not fabricate material issues", "spares_used.all().update" not in workflow or "reservation_status='ISSUED'" not in workflow, "TECO bulk-marks planned materials as ISSUED")

# 8. Procurement / services / invoices / business closure.
po_model = class_source("asset_mgmt/models.py", "PurchaseOrder")
ses_model = class_source("asset_mgmt/models.py", "ServiceEntrySheet")
check("QA-02 PO type derives from material/service requirement", "expected_po_type" in po_model and "source_operation.service_item" in po_model, "PO type derivation remains source_operation-only")
check("QA-03 New PO is forced to DRAFT", "self.status = 'DRAFT'" in po_model, "PO create status not forced")
check("Goods receipts require released Material PO", "MATERIAL" in class_source("asset_mgmt/models.py", "GoodsReceipt") and "RELEASED" in class_source("asset_mgmt/models.py", "GoodsReceipt"), "GR PO control missing")
check("QA-11 SES cumulative quantity/value ceilings", "accepted_qty" in ses_model and "accepted_amount" in ses_model and "PO balance" in ses_model, "SES cumulative cap missing")
check("Vendor invoices require receipt/service completion", "fully received / service accepted" in class_source("asset_mgmt/models.py", "VendorInvoice"), "Invoice readiness guard missing")
check("Vendor invoice clear/hold/payment actions exist", "def vendor_invoice_action" in views and all(x in views for x in ["release_payment", "Only Pending/Hold invoices can be cleared", "Accounts clearance is required"]), "Invoice controlled actions missing")
check("PO controlled action endpoint exists", "def purchase_order_action" in views and "purchase_order_action" in urls, "PO transition endpoint missing")
check("QA-12 Business close requires PR/PO final closure", "every purchase request must be closed/cancelled/rejected" in workflow.lower() and "every linked purchase order must be financially/operationally closed" in workflow.lower(), "WO close procurement gate missing")

# 9. TECO / time / downtime / financial closure.
check("QA-10 Labour entry is execution-phase gated", "IN_PROGRESS" in class_source("asset_mgmt/models.py", "WorkOrderLabour") and "TECO" in class_source("asset_mgmt/models.py", "WorkOrderLabour"), "Labour gate missing")
check("QA-23 Downtime blocked after TECO", "technical_lock" in class_source("asset_mgmt/models.py", "AssetDowntimeEvent"), "Downtime technical lock missing")
check("Financial settlement rules required", "settlement rules must total 100" in workflow.lower() and "settle_work_order" in workflow, "Settlement gate missing")

# 10. PM / meter / reliability / scoping.
asset_meter_reading = class_source("asset_mgmt/models.py", "AssetMeterReading")
check("QA-19 Multiple same-day asset-meter readings allowed", "uniq_asset_meter_reading_date" not in asset_meter_reading and "reading_date'" not in asset_meter_reading.split("constraints",1)[-1] if "constraints" in asset_meter_reading else True, "Per-day unique constraint remains")
check("QA-20 Latest chronological meter reading is authoritative", "latest = self.meter.readings.order_by('-reading_date', '-created_at').first()" in asset_meter_reading and "current_reading = latest.reading" in asset_meter_reading, "Meter correction/current reading logic missing")
check("PM durable call history exists", "class PMCall" in models and "ensure_due_pm_call" in pm_service, "PMCall occurrence model/service missing")
check("QA-21 PM compliance uses durable PMCall denominator", "PMCall" in views and "pm_calls =" in views and "persisted_call_count" in views and "due_without_call" in views, "PM compliance still derived only from durable calls")
check("QA-22 Maintenance cost is transaction-period based", "calculate_maintenance_cost_for_period" in reliability and "posted_at__gte" in reliability and "accepted_at__gte" in reliability and "cost_closed_at__gte" in reliability, "Period cost helper missing")
check("MTTR uses completed breakdown repair actual times", "actual_start" in reliability and "actual_end" in reliability and "BREAKDOWN" in reliability and "completed_breakdown_repairs" in reliability and "total_repair_hours" in reliability, "MTTR source logic incomplete")
check("MTBF uses scoped assets, scheduled hours and breakdown downtime", "scheduled_hours" in reliability and "breakdown" in reliability.lower() and "eligible_assets" in reliability and "total_operating_hours" in reliability, "MTBF scope/operating-hours logic incomplete")
check("Plant scoping helper covers PM/WO/meter/procurement", all(token in read("asset_mgmt/permissions.py") for token in ["pm_plan", "work_order", "meter", "purchase_order", "item"]), "Cross-module plant scope missing")

# 11. UI integrations missing in original QA.
for label, route in [
    ("QA-16 Asset BOM UI", "asset_bom_create"),
    ("Asset condition assessment UI", "asset_condition_assessment_create"),
    ("Asset criticality assessment UI", "asset_criticality_assessment_create"),
    ("QA-17 Inspection execution UI", "inspection_record_create"),
    ("QA-17 Calibration execution UI", "calibration_record_create"),
    ("QA-18 Shutdown-job update UI", "shutdown_job_update"),
]:
    check(label, route in urls and route in roles, f"{route} route/role mapping missing")

# 12. Dashboard defect.
check("QA-25 General dashboard includes CRITICAL assets", "criticality__in=['HIGH', 'CRITICAL']" in views or 'criticality__in=["HIGH", "CRITICAL"]' in views, "Critical asset query excludes CRITICAL")

# 13. Test suite includes remediation regression module.
check("QA remediation regression tests included", (ROOT / "asset_mgmt/tests/test_qa_remediation.py").exists(), "test_qa_remediation.py missing")

print("\nSummary")
print(f"  Passed: {len(PASSES)}")
print(f"  Failed: {len(FAILURES)}")
if FAILURES:
    print("\nRelease-gate failures:")
    for failure in FAILURES:
        print(f" - {failure}")
    sys.exit(1)
print("STATIC QA RELEASE GATE PASSED")

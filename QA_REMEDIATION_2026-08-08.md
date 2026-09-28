# Engineering CMMS — QA Remediation Report

**Remediated build date:** 2026-08-08  
**Source build:** `Engineering-CMMS-SAP-Style-Enterprise-PM-Dashboards.zip`  
**Scope:** PM workflow edge controls, MTTR/MTBF/reliability logic, plant scoping, work-order actions, reservations/materials, procurement, TECO, PM compliance, supporting execution modules, migration packaging and offline UI.

## Release status

**Source remediation: PASS. Runtime certification: PENDING target-machine Django execution/UAT.**

All 26 defects from the formal QA report have source-level fixes and are covered by the static QA release gate. The repaired source passes Python compilation, the project static validator, migration model/field comparison, route/role/template checks and a 56-assertion QA regression gate.

This report deliberately does **not** claim that `manage.py test` passed in the packaging sandbox: Django could not be installed in the isolated build environment. The project includes 46 Django test methods, including 15 remediation regression tests, for execution on the target machine.

## Defect remediation matrix

| QA defect | Remediation | Status |
|---|---|---|
| 1. TECO marked every planned material ISSUED | TECO now releases unused reservations and derives `ISSUED/PARTIAL/UNRESERVED` from posted material-issue usage. | FIXED |
| 2. Operation-level non-stock PR became Service PO | PO type is derived from the item/service requirement; an operation alone no longer forces Service. | FIXED |
| 3. PO status editable on create | `po_type` and `status` removed from PO form; new POs are system-forced to `DRAFT`; lifecycle uses explicit actions. | FIXED |
| 4. Need Info / Reject missing CSRF | CSRF tokens added; release gate scans every POST form. | FIXED |
| 5. Reserved stock could be transferred | Stock transfer subtracts active reservations from physical balance and blocks transfer of committed stock. | FIXED |
| 6. Operation predecessor not enforced | Enforced during scheduling, execution start/resume and confirmation. | FIXED |
| 7. Capacity ignored persons required | Work-centre utilization uses `planned_hours × persons_required`; daily capacity uses crew size. | FIXED |
| 8. `quantity_used` manually editable | Removed from planning form; usage is derived from posted material issues. | FIXED |
| 9. Material issue could post before release | Posting allowed only for `RELEASED`/`IN_PROGRESS` WOs before TECO and only for planned material. | FIXED |
| 10. Labour before execution | Labour restricted to execution/completion/verification window and blocked after TECO. | FIXED |
| 11. SES could exceed PO | Cumulative accepted service quantity and value are capped at PO quantity/value. | FIXED |
| 12. Business closure allowed open PO/PR | WO close requires PRs closed/cancelled/rejected and linked POs closed/cancelled plus settlement complete. | FIXED |
| 13. No WO reject/rework/cancel paths | Added `reject_approval`, `return_planning`, `return_execution`, `cancel` with mandatory reasons and validation. | FIXED |
| 14. WO self-approval | Creator cannot approve own WO. | FIXED |
| 15. Technician could control another technician's operation | Record-level technician ownership checks added to WO and operation actions/confirmations. | FIXED |
| 16. No Asset BOM UI | BOM create/update routes, forms and asset-detail actions added. | FIXED |
| 17. No inspection/calibration execution UI | Record list/create execution paths added for inspections and calibrations. | FIXED |
| 18. Shutdown jobs not updateable | Dedicated shutdown-job update path added. | FIXED |
| 19. One meter reading/day | Daily uniqueness removed; multiple IoT/manual readings per day are supported. | FIXED |
| 20. Downward meter correction did not become current | Current reading follows latest chronological reading, including documented correction. | FIXED |
| 21. PM compliance denominator unstable | Added durable `PMCall` occurrence/history; manager compliance uses persisted due calls plus due calls not yet persisted. | FIXED |
| 22. Maintenance cost not transaction-period based | Monthly/period cost uses posted material issues, labour timestamps, accepted service entries and cost-close date for other cost. | FIXED |
| 23. Downtime could be added after TECO | Model/view reject downtime linked to technically locked WOs. | FIXED |
| 24. No versioned migration | `asset_mgmt/migrations/0001_initial.py` is shipped. Snapshot generator now includes relationships and topologically orders 79 models; field-by-field gate validates it. | FIXED |
| 25. General dashboard omitted CRITICAL | Critical query now includes HIGH + CRITICAL + safety-critical. | FIXED |
| 26. Bootstrap/Chart CDN dependency | Core UI CSS, tabs and dashboard chart fallback are self-hosted under static assets; no external CDN references remain. | FIXED |

## Additional integration defects found during remediation

The remediation pass found and fixed several edge cases beyond the original report:

- Goods Receipt and Purchase Order ModelForms now derive hidden/system fields **before** `model.clean()` runs. This prevents valid GR/service-PO forms from failing because plant/item/type had only been set later in `form_valid()`.
- If the same spare is planned on multiple WO operations, a material issue without an operation is rejected as ambiguous instead of silently consuming the first matching plan line.
- Goods received specifically for a WO shortage automatically become a reservation for that planned material line, preventing the newly received stock from being transferred away before issue.
- Technician double-booking is detected during scheduling.
- PO lifecycle is controlled as `DRAFT → RELEASED → RECEIVED/INVOICED → CLOSED`; cancellation is blocked after receipt/service/invoice activity.
- Vendor invoice lifecycle is separated into entry, accounts clearance/hold, payment release and PO closure.
- Planning fields are locked after planning/approval; redesign uses the controlled Return to Planning action.
- `verify_system` now checks reservation-vs-physical stock, material issue ledger reconciliation, PO type, service/invoice ceilings, technical-lock consistency, predecessor integrity and post-TECO downtime.

## MTTR / MTBF / reliability controls

### MTTR

`MTTR = total actual repair duration of completed breakdown WOs / completed breakdown repairs with valid actual timestamps`

- Preventive/inspection/calibration work is excluded.
- Missing/invalid actual start/end records are excluded and surfaced as warnings.

### MTBF

`MTBF = total operating hours / number of breakdown failures`

Where operating hours are scheduled operating hours across in-scope active assets less merged breakdown downtime. Overlapping breakdown events are merged so downtime is not double counted.

### Scope

Reliability inputs use the same user plant scope as the underlying Asset, Work Order and Downtime querysets. Plant filters narrow the already-authorized scope; they do not grant new access.

## WO state-machine controls

The controlled lifecycle is:

`DRAFT → PLANNED → PENDING_APPROVAL → APPROVED → PREPARATION → READY_TO_SCHEDULE → SCHEDULED → DISPATCHED → RELEASED → IN_PROGRESS → COMPLETED → VERIFIED → TECO → COST_CLOSURE → CLOSED`

Exception paths are explicit and audited:

- Reject approval → Planned
- Return to planning
- Return to execution
- Cancel before execution commitments prevent safe cancellation

The order cannot be released until planning/procurement/permit/LOTO readiness checks pass. TECO creates a technical lock and financial settlement remains a separate later phase.

## Validation gates executed in packaging environment

- Python source compilation: PASS
- Project static URL/view/template/role validator: PASS
- POST-form CSRF scan: PASS
- No external core-UI CDN references: PASS
- Versioned migration exists: PASS
- Models vs migration model/field snapshot: PASS
- Local model migration dependency order: PASS (0 forward local FK/O2O/M2M references)
- QA release gate: **56/56 PASS**
- ZIP integrity: run at packaging stage

## Django regression suite

The project now contains **46** Django test methods. The remediation module covers, among other cases:

- WO self-approval rejection
- persons-required capacity
- predecessor confirmation blocking
- reserved-stock transfer blocking
- material issue lifecycle and overissue
- material-vs-service PO derivation
- service-entry cumulative limits
- multiple same-day meter readings and downward correction
- post-TECO downtime blocking
- TECO unused-material integrity
- business closure with open procurement
- goods-receipt-to-WO reservation integration
- PO ModelForm pre-validation derivation
- Goods Receipt ModelForm pre-validation derivation
- ambiguous multi-operation material issue rejection

## Required target-machine certification

Fresh database:

```bat
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py check
python manage.py verify_system
python manage.py collectstatic --noinput
python manage.py test
```

Existing database from an older no-migration build: back it up and, only if its tables match this release, use `python manage.py migrate --fake-initial` before the same checks/tests.

Then perform browser UAT using each real role and at least one complete breakdown cycle plus one PM cycle.

**Production approval remains conditional on:** zero failing Django tests, zero `verify_system` integrity errors, successful browser UAT, database backup/restore validation, and deployment/security review.

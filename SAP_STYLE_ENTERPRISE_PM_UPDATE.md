# SAP-Style Enterprise PM Update

This build upgrades the CMMS from an SAP-inspired work-order flow into a connected, SAP-style maintenance application for the defined industrial PM scope.

## Controlled lifecycle

Asset → Notification → Screening → Work Order → Planning → Approval → Preparation → Ready to Schedule → Scheduling → Dispatch → Release → Execution → Completion → Verification/Post Execution → TECO → Cost Settlement → Business Closed → Reliability.

Statuses cannot be freely edited from the work-order form. Server-side transition rules enforce the next permitted phase and its prerequisites.

## 12 enterprise PM enhancements

1. **Scheduling and dispatch** – work-centre capacity, operation dates, Ready to Schedule, Scheduled and Dispatched phases, scheduling board and capacity controls.
2. **Enhanced operations** – PRE/MAIN/POST stages, suboperations, predecessor relationships, control key, internal/external execution, manpower and planned hours.
3. **Operation confirmations** – partial/final confirmation, actual/remaining work, pause/resume/work-finished events and operation actual hours.
4. **Operation-level materials** – components are attached to individual work-order operations.
5. **Inventory reservation** – physical, reserved and available stock are separated; reservations protect stock from consumption by unrelated work orders.
6. **Automatic non-stock procurement** – shortages/non-stock requirements create a purchase request linked to the work order and source operation.
7. **External services** – external operations use service items, service PR/PO and accepted Service Entry Sheets for actual cost.
8. **Notification catalogs** – structured notification items with object-part, damage, cause and activity codes in addition to free-text reporting.
9. **Reusable maintenance task lists** – General, Equipment and Functional Location task lists with reusable operations, materials, tools, safety instructions and strategy packages.
10. **Preventive-maintenance engine** – fixed/completion-based calendar plans, running-hours plans, additional counters, maintenance strategies and package calls.
11. **Condition-based maintenance** – meter threshold rules can automatically create maintenance notifications; counter readings drive PM due logic.
12. **Technical and financial completion** – TECO locks technical changes, closes reservations and restores the asset; settlement rules allocate actual costs to cost-centre/asset/WBS/internal-order references before business closure.

## Role dashboards

### Maintenance Manager Dashboard
For HOD / Manager / Admin. It includes:
- PM compliance and due/counter-due plans
- MTTR, MTBF, availability and failure rate
- Monthly maintenance cost
- Backlog, approval queue and overdue work orders
- Ready-to-schedule queue
- Work-centre capacity/utilisation
- Recent breakdown work
- Links to Scheduling Board and Maintenance History & Reliability

### Engineering / Maintenance Technician Dashboard
For maintenance execution. It focuses on assigned work, PM work, permits, execution and engineering workload.

### Asset Admin Dashboard
For Asset Admin / HOD / Manager / Admin. It includes total, active, critical, running, stopped, breakdown and maintenance assets plus lifecycle, plant, functional-location and category views.

### General Dashboard
Remains available to other permitted roles, with role-scoped operational summary data.

## Reliability formulas

- MTTR = total actual completed breakdown repair hours / completed breakdown repairs
- MTBF = operating hours / breakdown failures
- Operational Availability = operating hours / scheduled hours × 100
- Failure Rate = failures / operating hours × 1,000

Breakdown downtime intervals are merged so overlapping downtime records are not double-counted.

## Important scope note

This project implements the defined **SAP-style maintenance behavior** inside a standalone CMMS. It is not a literal copy of the full SAP S/4HANA product suite. SAP also relies on separately configured FI/CO, MM, HR, EWM and enterprise integration services. Here, the equivalent maintenance-side behaviors are implemented locally so the CMMS can operate independently.

## Database update

This build adds models and fields. After extraction run:

```bat
python manage.py makemigrations asset_mgmt
python manage.py migrate
```

For an existing production database, back up the database before migration.

## Validation

The package includes regression tests in `asset_mgmt/tests/test_sap_pm_enhancements.py` plus the existing workflow/reliability tests. Run locally after installing requirements:

```bat
python manage.py check
python manage.py test
```

The packaging environment did not contain/install Django from its configured package source, so live Django runtime tests could not be executed during packaging. Python compilation and static reference checks were performed before release.

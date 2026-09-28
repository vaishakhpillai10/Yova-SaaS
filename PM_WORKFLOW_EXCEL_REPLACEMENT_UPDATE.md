# PM Workflow + Engineering History Excel Replacement Update

This build extends the corrected MTTR/MTBF package so the CMMS can replace the company's `ENGG HISTRY.xlsm` maintenance-history workflow and use a controlled SAP-style PM lifecycle.

## 12 Excel-replacement features added

1. **Maintenance History & Reliability** screen in the main navigation.
2. **From / To date filtering** (covers monthly and custom reporting periods).
3. **TAG / Asset filtering**.
4. **Work Centre filtering**.
5. **Criticality filtering**.
6. **Work Type + Activity Type filtering** (e.g. Breakdown + Greasing/Testing/Repair).
7. **Permit Type filtering**.
8. **Shift** field on Work Orders (`General`, `A`, `B`, `C`) plus report filter.
9. **Supervisor** field separate from assigned technician and verifier.
10. **Failure Rate / 1,000 operating hours** KPI, in addition to MTTR, MTBF and Availability.
11. **Excavation Work** added to Permit-to-Work types.
12. **Excel and PDF export** of filtered maintenance history and reliability KPIs.

The history report includes work order, permit, TAG, equipment, work centre, criticality, work/activity type, spares consumed, shift, repair time, technician, supervisor, actual cost and remarks.

## Controlled PM workflow implemented

```text
ASSET
  ↓
NOTIFICATION / MAINTENANCE REQUEST
  ↓
SCREENING
  ├─ Need More Information
  ├─ Rejected
  └─ Accepted
  ↓
WORK ORDER (DRAFT)
  ↓
PLANNING
  ├─ Operations
  ├─ Technician
  ├─ Supervisor
  ├─ Planned Materials
  ├─ Tools
  ├─ Permit requirement
  ├─ Risk assessment
  └─ Estimated cost
  ↓
PLANNED
  ↓
PENDING APPROVAL
  ↓
APPROVED
  ↓
PREPARATION
  ↓
RELEASED
  ↓
IN PROGRESS
  ├─ Actual start/end
  ├─ Material issue
  ├─ Labour
  ├─ Downtime
  └─ Failure data
  ↓
COMPLETED
  ↓
VERIFIED
  ↓
TECO
  ↓
COST CLOSURE
  ↓
CLOSED
  ↓
RELIABILITY
MTTR | MTBF | Availability | Failure Rate | Cost | Failure History
```

### Workflow safeguards

- Work Order status is no longer freely editable from the ordinary Work Order form.
- Planning requires technician, supervisor, planned dates and at least one operation.
- Approval is a separate controlled transition.
- Release checks required issued permit, LOTO, risk assessment and planned-material stock availability.
- Start Work automatically records actual start and marks the asset operational status as `MAINTENANCE`.
- Completion requires all operations completed/cancelled, completion notes and failure mode/cause for breakdown work.
- TECO requires permits closed, no draft material issues, and breakdown downtime when the originating notification says production stopped.
- Cost Closure calculates actual cost from posted material issues + labour + external service + other cost.
- Closing the Work Order closes the linked notification.
- PM completion updates `last_completed_date` when the PM Work Order reaches TECO/Closed.

## Permit workflow

Permit status is controlled instead of freely selected:

`Requested → Safety Review → Approved → Issued → Closed`

A required permit must be **Issued** before Work Order release and must be **Closed** before TECO.

## PM generation

Calendar PM generation now creates a Draft Work Order and converts PM tasks into structured Work Order Operations. The planner then assigns/validates the supervisor and follows the normal workflow.

## Reliability formulas

- **MTTR** = total actual repair duration of completed breakdown Work Orders / completed breakdown repairs.
- **MTBF** = operating hours across eligible assets / breakdown failures.
- **Availability** = operating hours / scheduled hours × 100.
- **Failure Rate / 1,000 h** = breakdown failures / operating hours × 1,000.
- Breakdown downtime intervals are merged so overlapping downtime is not double-counted.

## Database setup after extracting this version

Because this build adds database fields/models, run migrations before starting the server:

```bat
cd /d "D:\Aravind\ENG-SaaS\Engineering-CMMS-Modular-AssetAdmin-ClientData"
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt
python manage.py makemigrations asset_mgmt
python manage.py migrate
python manage.py check
python manage.py test
python manage.py runserver
```

For a completely fresh demo database, you can then run:

```bat
python manage.py seed_demo_data
```

## Validation note

The package-level Python compilation and static URL/template/permission validation pass. Full Django runtime tests could not be executed in the packaging environment because the environment could not download the required Django dependency. Run `python manage.py check` and `python manage.py test` in the project's virtual environment after installing `requirements.txt`.

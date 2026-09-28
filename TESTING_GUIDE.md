# Manual Testing Guide — Observations 1 to 24

Start the server, open `http://127.0.0.1:8000/`, and use the accounts in `DEMO_CREDENTIALS.md`. Mark each test Pass or Fail.

| No. | Login / test action | Expected result |
|---:|---|---|
| 1 | Login as `admin`. On Dashboard select a plant, click KPI cards, inspect pie/bar/line charts. | Cards open correctly filtered lists; charts and totals change with plant. |
| 2 | As `maintenance_engineer`, open Downtime and add an event for a critical asset. Return to dashboard/asset detail. | Downtime hours and availability are calculated without overlapping/negative duration. |
| 3 | Open Dashboard. | The old workflow strip is not shown. |
| 4 | Login as `maintenance_engineer`, choose PL01 and inspect lists. Try changing URL plant to an unassigned plant. | Only permitted plant records are visible; unauthorised records are blocked. |
| 5 | Create an MR and a WO without entering document numbers. | Unique numbers such as `MR-PL01-...` and `WO-PL01-...` are generated automatically. |
| 6 | Open Asset Register and create an asset using Plant, Area and Functional Location. | Logical location/asset hierarchy is saved and plant mismatch is rejected. |
| 7 | Login as HOD and create/inspect Mechanical, Electrical or Instrument assignments. Create a WO for one work centre. | The correct work centre and assigned users are available; other-plant choices are hidden. |
| 8 | Create a PM plan, add PM tasks, then click Generate WO. | One preventive WO is generated with ordered tasks, safety notes and tools; duplicate open WO is blocked. |
| 9 | As engineer create MOC and submit. As `maintenance_hod` approve with remarks. Open PDF. | Self-approval is blocked; status becomes Approved; record is locked; approval PDF opens. |
| 10 | Create RCA with 5-Why fields, then add Fishbone causes. | Both RCA methods and six Fishbone categories can be recorded. |
| 11 | Create CAPA with severity, probability and detectability. | Score is calculated/displayed; owner, due date, evidence and effectiveness fields are saved. |
| 12 | Create LLF observation and click Create MR. | LLF record is saved with sense/severity and creates one linked MR only. |
| 13 | Create a PR linked to a WO, then follow approval to PO. | The PR remains connected to maintenance while Purchase processes it in MM. |
| 14 | Download asset CSV template. Upload once with Validate Only, then import. Upload duplicate tag. | Validation preview works; valid rows import atomically; duplicate is rejected with line error. |
| 15 | Create Shutdown Plan and Shutdown Jobs with progress. Open Shutdown page. | Completion percentage and shutdown bar chart are shown. |
| 16 | Login as `purchase` and open MM Dashboard. | Approved/pending PRs, POs and procurement KPIs are shown. |
| 17 | Login as `store` and open Store Dashboard. | Stock value, low/zero stock, location balances and movements are shown. |
| 18 | Add an item with description, rate, min/max, UOM and vendor. Post a receipt. | Quantity comes from the ledger and stock value updates; quantity is not manually editable. |
| 19 | Add a Utility Meter and Meter Reading, then open Utility Dashboard. | Consumption and target/variance charts appear for utility/electrical types. |
| 20 | Login as engineer/HOD and open Engineering Dashboard. | One common dashboard displays engineering work scoped to the user’s permitted plant/work centre. |
| 21 | Create CAPEX, submit, approve as assigned approver, open Note. | Approval workflow works, self-approval is blocked and PDF note opens. |
| 22 | Create disposal request, submit, approve, execute. | Asset moves to Disposal Pending only after submit and Scrapped only after execution; record is retained. |
| 23 | Compare `maintenance_engineer` and `maintenance_hod` dashboards and actions. | Engineer sees assigned execution work; HOD sees team/overdue/approval information. |
| 24 | Engineer creates PR → submits. HOD rejects with reason → engineer edits/resubmits → HOD approves → Purchase marks Processing and creates PO. | Every transition is controlled, history is preserved, self/wrong-user approval fails, and unapproved PR cannot create PO. |

## Final integrity test

From the project terminal:

```bash
python manage.py backup_data
python manage.py verify_system
python manage.py test
```

All three commands must finish without an error before deployment.

## Responsive dashboard regression — 2026-08-16

| Test | Scenario | Expected result |
|---:|---|---|
| D1 | Open Common dashboard at 1440px, 1024px, 768px and 390px widths. | KPI cards and charts reflow without horizontal page overflow; mobile sidebar is off-canvas. |
| D2 | Use plant filter on Common/Asset/Manager dashboards. | KPI and chart data remain within the selected permitted plant. |
| D3 | Open Asset dashboard with HIGH/CRITICAL/safety-critical assets. | Critical count/watch include all three classifications. |
| D4 | Open Maintenance Manager dashboard with no PM calls due. | PM compliance displays N/A rather than 100%. |
| D5 | Click an Open Work Order status bar. | Work-order list opens with the matching `status` filter. |
| D6 | Click Open Breakdowns on Manager dashboard. | Work-order list is filtered to `work_type=BREAKDOWN`. |
| D7 | Enter a plant/category/location label containing `<`, `>` or `&`, then open dashboard. | Dashboard script remains valid; label is rendered as data and cannot break the script. |
| D8 | View a chart with no matching records. | A clear “No data available for this scope” state is shown. |

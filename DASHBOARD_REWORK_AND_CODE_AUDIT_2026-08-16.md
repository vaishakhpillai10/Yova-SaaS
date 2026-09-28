# CMMS Dashboard Rework & Full Static Code Audit — 16 Aug 2026

## Scope
This build is based only on `Engineering-CMMS-QA-Remediated-PM-Controls-Reliability-Fix.zip` and retains the Django 5.2 reliability-query correction.

## Dashboard redesign
### Common / Operations dashboard
- Professional responsive KPI grid.
- Current-month reliability strip for MTTR, MTBF, availability, breakdown downtime, failures and failure rate.
- Open work-order pipeline chart.
- Open maintenance requests by plant.
- Current-period downtime events by type.
- Critical-asset availability chart.
- Responsive recent WO / notification tables.
- Role-aware links: cards no longer send users to modules they cannot access.

### Asset dashboard
- Accurate active-asset count based on `Asset.is_active`.
- Running/readiness percentage and responsive readiness bar.
- Operational status, lifecycle, plant, functional-location and category visualizations.
- Critical asset watch with current operational status.
- Plant filter preserved across relevant drill-downs.

### Maintenance Manager dashboard
- PM compliance, MTTR, MTBF, availability, failure rate and transaction-period cost KPIs.
- Backlog, open breakdown, approval, scheduling, utilization and overdue controls.
- PM completed vs due/missed visualization.
- Work-order pipeline visualization.
- Seven-day work-centre capacity utilization visualization.
- Maintenance cost mix visualization.
- Due PM, scheduling queue, capacity table and recent breakdown tables.

## Data / integration corrections made during re-audit
1. Common-dashboard critical scope now includes `HIGH`, `CRITICAL`, and safety-critical assets.
2. Critical availability uses the same corrected critical scope.
3. Common request-by-plant chart now shows the open request backlog rather than mixing closed records.
4. Downtime-by-type chart is aligned to the current dashboard reporting period.
5. Asset active count uses the model's `is_active` flag rather than a partial lifecycle list.
6. Asset Register active summary uses the same `is_active` rule.
7. Work-order list now processes `work_type`, `activity`, and `shift` query filters used by dashboard drill-downs.
8. Purchase users route to the MM dashboard; Store users route to the Store dashboard.
9. Common-dashboard cards and actions are permission-aware for roles that remain on the general dashboard.
10. Inline dashboard JSON escapes HTML-significant characters so plant/category/location labels cannot terminate an inline script.
11. PM compliance no longer reports a misleading 100% when there are no PM calls due in the period; it displays N/A.
12. Currently-due PM plans are checked against calls in the current reporting period, so historical due/generated rows do not hide a current due plan.
13. Work-centre rows are sorted by utilization so overloaded/most-loaded centres are visible first.
14. The previously fixed `select_related()` + `only()` reliability FieldError protection remains in place.

## Responsive / offline UI corrections
- Added missing `col-md-*` and `col-xl-*` layout utilities used throughout dashboard templates.
- Rebuilt dashboard grids for desktop, tablet and mobile breakpoints.
- Added mobile off-canvas navigation instead of rendering the entire sidebar above dashboard content.
- Rebuilt self-hosted chart fallback with ResizeObserver-based redraw, high-DPI canvas rendering, vertical/horizontal bars, doughnut charts, labels, empty states and click hit-testing.
- No external CDN is required for core dashboard UI/charts.

## Static validation performed
See `FULL_STATIC_QA_2026-08-16.txt` for the machine-readable result. The gate checks:
- Python AST parsing and compileability.
- Duplicate/missing named URLs.
- URL tags in templates.
- CSRF on all POST forms.
- Template extends/static references.
- Balanced Django template control blocks.
- External CDN references.
- Migration presence.
- Reliability regression fix presence.
- Responsive dashboard classes.
- Safe inline chart JSON.
- Dashboard work-type drill-down support.
- Role dashboard routing.
- Criticality and active-asset metric rules.

## Runtime validation requirement
This packaging environment cannot reach the Python package index, so Django cannot be installed here. Run the following on the target Mac before production/UAT:

```bash
source .venv/bin/activate
python manage.py check
python manage.py migrate
python manage.py test
python manage.py verify_system
python manage.py runserver
```

Then complete browser UAT at desktop, tablet and mobile widths for Admin, Asset Admin, Maintenance Engineer, HOD/Manager, Store, Purchase, Safety, Production and Accounts roles.

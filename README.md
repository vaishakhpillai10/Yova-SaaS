# Engineering CMMS - Modular Asset Admin Build

This is a reusable CMMS base prepared from the earlier 24-observation project. This version focuses on a professional dashboard UI, Asset Admin role, module-wise product structure, and Asset Register / Asset Master readiness.

## Enterprise PM / SAP-style maintenance

This version now includes a controlled maintenance lifecycle, operation-level planning, scheduling/dispatch, confirmations, stock reservations and maintenance procurement, notification catalogs, reusable task lists, calendar/counter/strategy/condition-based PM, TECO and settlement, plus separate Maintenance Manager, Engineering and Asset Admin dashboards. See `SAP_STYLE_ENTERPRISE_PM_UPDATE.md`.

## Main changes

- Added a separate `Asset Admin` login.
- Added dedicated Asset Admin Dashboard.
- Asset Admin sees only asset-focused navigation.
- Asset Admin can view/register/edit/import assets and access asset status/transfer/change flows.
- Improved the dashboard UI system: collapsible sidebar, clean topbar, professional cards, better spacing, polished tables, smoother transitions.
- Kept the project reusable for future clients using module-wise business grouping.
- Fixed the Asset Status audit logging test issue.
- Kept real-data import command available for the client-data build.

## Setup

```bat
py -m venv .venv
call .venv\Scripts\activate.bat
pip install -r requirements.txt
py manage.py makemigrations
py manage.py migrate
py manage.py seed_demo_data
py manage.py collectstatic --noinput
py manage.py test
py manage.py runserver
```

Open: `http://127.0.0.1:8000/`

## Main logins

```text
admin / Admin@12345
asset_admin / Asset@12345
maintenance_engineer / Demo@12345
maintenance_hod / Demo@12345
manager / Demo@12345
```

## Real data import

Only use this in the client-data build after tests pass:

```bat
py manage.py import_real_engineering_data --dry-run
py manage.py import_real_engineering_data
```

Generated HOD users from real data use password: `RealData@123`.

## Documentation

- `docs/MODULE_ARCHITECTURE.md`
- `docs/ASSET_REGISTER_TESTING_FLOW.md`
- `docs/ASSET_REGISTER_IMPLEMENTED_SCOPE.md`
- `DEMO_CREDENTIALS.md`

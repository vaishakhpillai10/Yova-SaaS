# MTTR / MTBF correction update

## Updated files

- `asset_mgmt/services/reliability.py` — new centralized reliability KPI calculation service.
- `asset_mgmt/views.py` — dashboard now uses the corrected service.
- `asset_mgmt/templates/asset_mgmt/dashboard.html` — clearer KPI labels, units, calculation basis and data-quality warnings.
- `asset_mgmt/models.py` — completed breakdown work orders now require actual start and actual end.
- `asset_mgmt/tests/test_reliability.py` — focused tests for formulas, overlapping downtime and missing timestamps.
- `docs/RELIABILITY_KPI_IMPLEMENTATION.md` — implementation and user-entry documentation.

## Corrected formulas

- `MTTR = completed breakdown actual repair hours / valid completed breakdown repairs`
- `MTBF = operating hours across eligible assets / breakdown failures`
- `Operating hours = scheduled hours - merged breakdown downtime`

Only breakdown records affect the calculations. Overlapping downtime records for the same asset are merged and counted once.

## Validation completed

- Python bytecode compilation: passed.
- Project static validation script: passed.
- ZIP integrity test: to be run during packaging.

The full Django test suite could not be executed in the packaging environment because the required Django package was not available from its package source. Focused Django tests have been included in the project for execution in the normal project environment.

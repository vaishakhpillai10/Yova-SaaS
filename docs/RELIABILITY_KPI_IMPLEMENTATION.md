# MTTR and MTBF implementation

The dashboard Reliability Snapshot reports the current calendar month up to the current time and respects the logged-in user's plant scope.

## MTTR

`MTTR = total actual repair hours / completed breakdown repairs`

Only work orders with:

- Work type: `BREAKDOWN`
- Status: `COMPLETED`, `VERIFIED`, or `CLOSED`
- Actual end inside the reporting period
- Valid `actual_start` and `actual_end`

are included. Preventive, corrective, inspection, calibration, shutdown, safety and modification work orders do not affect MTTR. A completed breakdown work order without valid actual timestamps is excluded and a dashboard warning is shown.

## MTBF

`MTBF = total operating hours / number of breakdown failures`

Where:

`total operating hours = scheduled hours of eligible assets - merged breakdown downtime`

The calculation:

- Uses `scheduled_hours_per_day` for assets in an operating lifecycle state (`ACTIVE`, `OPERATIONAL`, `STANDBY`, `TEMP_INACTIVE`, `UNDER_MAINTENANCE`, or `BREAKDOWN`). Scrapped and inactive assets are excluded.
- Accounts for commissioning, decommissioning and disposal dates.
- Includes only downtime type `BREAKDOWN`.
- Clips downtime to the reporting period.
- Merges overlapping downtime intervals per asset, preventing double counting.
- Treats one non-cancelled breakdown work order as one failure.
- Uses `actual_start` as the failure date, falling back to `created_at` when actual start is missing.

## User data-entry requirements

1. Create one breakdown work order for each equipment failure.
2. Record `actual_start` when repair work begins.
3. Record `actual_end` when repair work finishes.
4. Complete, verify or close the work order.
5. Record equipment downtime with type `BREAKDOWN`, preferably linked to the relevant work order.
6. Maintain each asset's `scheduled_hours_per_day` accurately.

## Data-quality control

The Work Order form now prevents a breakdown work order from being marked `COMPLETED`, `VERIFIED`, or `CLOSED` until both `actual_start` and `actual_end` are entered. Existing legacy records with incomplete timestamps are excluded from MTTR and shown as a dashboard warning.

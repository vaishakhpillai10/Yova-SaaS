# Known Limitations and Production Checklist

- This is a standalone **SAP-style CMMS**, not the proprietary SAP S/4HANA codebase. It implements the defined maintenance behaviors locally rather than connecting to SAP FI/CO, MM, HR, EWM or BTP by default.
- Runtime Django checks and tests must be run on your computer during setup. The packaging environment could perform Python/static validation but could not install Django packages from its configured package source.
- Local SQLite is suitable for development/testing only. Use PostgreSQL in production.
- Core layout utilities, tabs and dashboard charts are self-hosted under `asset_mgmt/static`; the application does not require an external UI/chart CDN for its core interface.
- The built-in login throttle uses local-memory cache. Use Redis for multiple production server instances.
- Schedule `generate_due_pm_work_orders` using Windows Task Scheduler, cron or your production job runner for unattended PM generation.
- Calendar, running-hour, additional-counter, maintenance-strategy/package and condition-threshold logic are implemented. Real IoT ingestion still requires an external device/API connector.
- Settlement rules/postings provide CMMS-side financial closure. Posting into a real ERP general ledger requires a dedicated accounting/API integration.
- External-service procurement includes service PR/PO and Service Entry Sheet acceptance. Supplier portal/e-invoicing integrations require external connectors.
- Before production: run database backup/restore tests, Django test suite, UAT, concurrency/load tests, security review, permission review and deployment hardening.

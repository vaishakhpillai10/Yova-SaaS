# CMMS Modular Architecture

This build is prepared as a reusable CMMS base product. The current model layer is kept stable to avoid migration breakage, while the product is organized by business modules and role-based navigation.

## Business modules

| Product module | Django area / responsibility |
|---|---|
| Core | Company, Plant, Department, Area, Functional Location, Work Centre, Cost Centre |
| Accounts | Users, roles, module access, plant assignment |
| Dashboard | Global dashboard and role redirection |
| Asset Register | Asset Admin dashboard, Asset Master CRUD, import, documents, images, QR, status, transfer, history |
| Maintenance | Maintenance Requests, Work Orders, Downtime |
| Planning | PM, Shutdown, RCA, CAPA, LLF/TPM, MOC, Inspection, Calibration, Permit to Work |
| Materials | Item Master, PR, PO, MIGO, Stock Transfer, Material Issue, Vendor Invoice |
| Utilities | Utility Dashboard, Meters, Readings |
| Approvals | CAPEX, Asset Disposal |
| Audit | Audit log and history traceability |

## Why this structure

The project should be reusable for multiple clients. A client may need only Asset Register, while another may need Asset Register + Maintenance + Materials. The navigation and permissions are therefore controlled by roles and module access.

## Current implementation rule

Do not split the database models into many apps suddenly without a migration plan. The safer production path is:

1. Stabilize the working Asset Register module.
2. Finish the reusable UI and role permissions.
3. Move one business domain at a time into separate Django apps only after tests exist.
4. Keep old data safe using planned migrations.

## Asset Admin module

`Asset Admin` has a dedicated dashboard and asset-only sidebar. It can view all asset data, register assets, import assets, edit Asset Master records, change status, upload asset files, and create asset transfer/change requests.

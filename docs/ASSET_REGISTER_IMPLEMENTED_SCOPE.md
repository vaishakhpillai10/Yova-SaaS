# Asset Register Implemented Scope

This build implements the practical foundation of the PDF update:

- Asset ID generation through `DocumentSequence`.
- Plant, Department, Area, Functional Location and Cost Centre fields.
- Asset ownership and responsibility fields.
- Parent/child asset hierarchy validation.
- Lifecycle status separated from operational status.
- Controlled status-change action with `AssetStatusHistory`.
- Technical, procurement, warranty, AMC, criticality, safety, condition, meter and QR fields.
- Asset document metadata and approval status fields.
- Multiple image support through `AssetImage`.
- Asset meter and meter reading records.
- Asset transfer request workflow.
- Asset change request workflow.
- Enhanced Asset Register list and tabbed Asset Detail UI.
- CSV template import and command-line real Excel importer.

The project is still a testing build. Production hardening should include complete approval routing for every asset change request, object storage for files, and final client field naming confirmation.

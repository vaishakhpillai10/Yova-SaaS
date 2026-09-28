# Asset Register Testing Flow

Test only the Asset Register section first.

## 1. Login and page opening

1. Login as `admin / Admin@12345`.
2. Open **Asset Register**.
3. Confirm KPI cards are visible: Total Assets, Active Assets, Critical/Safety, Warranty Expiring.
4. Confirm filters are visible: Plant, Category, Lifecycle, Operational, Condition.
5. Open any asset from the table.

Expected: Asset detail opens with tabs: Overview, Technical, Hierarchy, Maintenance, Documents, BOM & Spares, Meters, History and QR.

## 2. Real Excel import

The real Excel files are already placed in `data_imports/`.

Run:

```bat
py manage.py import_real_engineering_data --dry-run
```

If the row count looks correct, run:

```bat
py manage.py import_real_engineering_data
```

Expected: thousands of assets, functional locations, work centres and one disposal request are created.

## 3. Create one new asset manually

Go to **Asset Register → Add Asset** and enter this sample:

```text
Plant: choose first plant
Functional Location: choose a location from the same plant
Asset Type: Pump
Tag Number: TEST-PUMP-001
Name: Test Transfer Pump
Description: Test pump created for Asset Master verification
Category: choose any available category
Lifecycle Status: Active
Operational Status: Running
Criticality: High
Criticality Score: 75
Safety Critical: Yes
Manufacturer: Test Pumps Pvt Ltd
Model Number: TP-100
Serial Number: TP-SN-001
Purchase Date: 2025-04-01
Commissioning Date: 2025-05-01
Warranty Start Date: 2025-05-01
Warranty End Date: 2027-05-01
Scheduled Hours Per Day: 24
Availability Target: 95
```

Expected: the system generates an Asset ID automatically and opens/saves without duplicate errors.

## 4. Duplicate prevention

Try creating another asset in the same plant with:

```text
Tag Number: TEST-PUMP-001
```

Expected: the system blocks it because tag number must be unique inside the plant.

## 5. Asset detail tabs

Open the test asset and check:

- Overview tab shows plant, location and responsibility.
- Technical tab shows manufacturer/model/serial.
- Hierarchy tab shows parent/child asset area.
- Maintenance tab shows WO/PM/downtime links.
- Documents tab has Add Document and Add Image.
- Meters tab has Add Meter and Record Reading.
- History tab shows status history.
- QR tab shows QR token/value.

## 6. Controlled status test

On the asset detail page, use **Controlled Status Action**:

```text
Lifecycle: Active
Operational: Under Maintenance
Effective Date: today
Reason: Testing status control
```

Expected: status changes and a new history line appears in the History tab.

## 7. Transfer request test

1. Go to **Asset Detail → Transfer**.
2. Select the same asset.
3. Select destination plant/location.
4. Enter reason: `Testing controlled asset transfer`.
5. Save.

Expected: transfer request is created. The asset location should not change immediately. Location should change only after the transfer workflow reaches receive/complete.

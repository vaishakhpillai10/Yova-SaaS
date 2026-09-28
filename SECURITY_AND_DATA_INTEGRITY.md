# Security and Data Integrity

The integrated build includes the following controls:

- Plant-scoped querysets and foreign-key choices.
- Explicit role-to-URL permissions plus record-level checks.
- Assigned-approver checks and self-approval prevention.
- POST-only workflow and stock-posting actions with CSRF protection.
- `transaction.atomic()` and `select_for_update()` for numbering, approvals, PO conversion and stock posting.
- Database uniqueness constraints for document numbers, plant codes, item/location balances and one PO per PR.
- `PROTECT` on important business relationships to reduce accidental record loss.
- Posted stock records use an immutable transaction ledger; negative material issue is blocked.
- Audit logs store user, action, object, previous/new values, timestamp, IP and remarks.
- Uploaded file type/size validation.
- Password validators, HTTP-only session cookies, session expiry, secure headers and login throttling.
- Environment variables for secrets, hosts, database URL, HTTPS cookies, SSL redirect and HSTS.
- `backup_data` and `verify_system` management commands.
- Automated tests for numbering, plant isolation, PR approval, inventory and protected views.

## Data-safety rule

No application can honestly guarantee zero data loss. For real use, configure PostgreSQL, automated backups, off-site copies and regular restore tests. Run this before major changes:

```bash
python manage.py backup_data
python manage.py verify_system
```

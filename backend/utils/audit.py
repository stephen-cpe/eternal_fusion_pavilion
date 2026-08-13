"""
Shared audit-logging helper used by all admin route modules.

Previously, `log_audit` was duplicated verbatim in `routes/admin_blocks.py` and
`routes/admin_reservations.py`. Extracted here to keep a single source of truth.
"""
from models import AuditLog
from database import db


def log_audit(admin_id, action, entity_type, entity_id, details):
    """Create an AuditLog row on the current session.

    The caller is responsible for committing the session (this helper only
    stages the row). On failure, the error is logged and swallowed so a
    broken audit entry never rolls back the business operation it records.
    """
    try:
        log_entry = AuditLog(
            admin_id=admin_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )
        db.session.add(log_entry)
    except Exception as e:
        print(f"Error logging audit trail: {e}")
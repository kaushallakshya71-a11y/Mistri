"""
Mistri Audit Logging Service
Enterprise audit trail tracking for critical system operations and compliance.
"""
import json
import logging
from typing import Optional, Union, Dict, Any
from db.database import get_db

logger = logging.getLogger("mistri.audit")

def log_audit_event(
    user: Optional[Dict[str, Any]],
    action: str,
    entity: str,
    entity_id: Union[str, int],
    details: Optional[Union[str, Dict[str, Any]]] = None,
    ip_address: Optional[str] = None
) -> None:
    """
    Record an immutable audit event in the database.
    """
    user_id = user.get("id") if user else None
    user_name = user.get("name") if user else "System/Anonymous"
    user_role = user.get("role") if user else "system"

    if isinstance(details, (dict, list)):
        details_str = json.dumps(details)
    else:
        details_str = str(details) if details is not None else None

    try:
        conn = get_db()
        conn.execute("""
            INSERT INTO audit_logs (user_id, user_name, user_role, action, entity, entity_id, details, ip_address)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, user_name, user_role, action, entity, str(entity_id), details_str, ip_address))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to record audit log: {e}")

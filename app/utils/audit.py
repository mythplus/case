import json
from app.models import AuditLog, db


def log_action(action, target_type, target_id, detail=None):
    """写入操作日志。"""
    if detail is not None and not isinstance(detail, str):
        detail = json.dumps(detail, ensure_ascii=False)
    entry = AuditLog(
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id else None,
        detail=detail,
    )
    db.session.add(entry)
    db.session.commit()

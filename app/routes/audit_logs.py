from flask import Blueprint, jsonify, request

from app.models import AuditLog, db

audit_logs_bp = Blueprint("audit_logs", __name__)


@audit_logs_bp.route("", methods=["GET"])
def list_audit_logs():
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 20, type=int)
    page_size = min(page_size, 100)
    action = request.args.get("action")
    target_type = request.args.get("target_type")

    q = AuditLog.query
    if action:
        q = q.filter(AuditLog.action == action)
    if target_type:
        q = q.filter(AuditLog.target_type == target_type)

    total = q.count()
    items = q.order_by(AuditLog.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return jsonify({
        "total": total,
        "page": page,
        "page_size": page_size,
        "logs": [i.to_dict() for i in items],
    }), 200

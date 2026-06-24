import uuid
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from app.models import Case, db

cases_bp = Blueprint("cases", __name__)


def _gen_case_id():
    now = datetime.now()
    prefix = f"c_{now.strftime('%Y%m%d')}_"
    last = (
        Case.query.filter(Case.case_id.startswith(prefix))
        .order_by(Case.case_id.desc())
        .first()
    )
    seq = 1
    if last:
        # case_id 格式: c_YYYYMMDD_NNN-xxxxx，取第三段下划线后的序号部分
        seq_part = last.case_id.split("_")[2].split("-")[0]
        seq = int(seq_part) + 1
    suffix = uuid.uuid4().hex
    return f"{prefix}{seq:03d}-{suffix[:4]}-{suffix[4:16]}"


@cases_bp.route("", methods=["POST"])
def create_case():
    data = request.get_json(force=True)
    required = ["agent_input", "agent_output"]
    missing = [f for f in required if f not in data or data[f] is None]
    if missing:
        return jsonify({"error": "Missing required fields", "missing_fields": missing}), 400

    case = Case(
        case_id=_gen_case_id(),
        run_time_ms=data.get("run_time_ms"),
        tokens_consumed=data.get("tokens_consumed"),
        source=data.get("source"),
        description=data.get("description"),
        category=data.get("category"),
        agent_input=data["agent_input"],
        agent_output=data["agent_output"],
    )
    db.session.add(case)
    db.session.commit()

    # 生成完整标注链接
    from flask import current_app
    base_url = current_app.config.get("BASE_URL", "http://localhost:5000")
    annotate_url = f"{base_url}/annotate/{case.case_id}"

    # 异步推送企微通知
    try:
        from app.utils.wecom import notify_cases
        notify_cases(
            [{"case_id": case.case_id, "source": case.source,
              "category": case.category, "annotate_url": annotate_url}],
            current_app._get_current_object(),
        )
    except Exception:
        import logging
        logging.getLogger(__name__).exception("企微通知发送失败")

    return jsonify({
        "case_id": case.case_id,
        "status": case.status,
        "created_at": case.created_at.isoformat(),
        "annotate_url": annotate_url,
    }), 200


@cases_bp.route("", methods=["GET"])
def list_cases():
    status = request.args.get("status")
    category = request.args.get("category")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    sort_by = request.args.get("sort_by", "created_at")
    sort_order = request.args.get("sort_order", "desc")
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 20, type=int)
    page_size = min(page_size, 100)

    q = Case.query
    if status:
        q = q.filter(Case.status == status)
    if category:
        q = q.filter(Case.category == category)
    if start_date:
        from datetime import datetime
        try:
            start_dt = datetime.fromisoformat(start_date)
            q = q.filter(Case.created_at >= start_dt)
        except ValueError:
            pass
    if end_date:
        from datetime import datetime
        try:
            end_dt = datetime.fromisoformat(end_date)
            q = q.filter(Case.created_at <= end_dt)
        except ValueError:
            pass

    col = getattr(Case, sort_by, Case.created_at)
    q = q.order_by(col.desc() if sort_order == "desc" else col.asc())
    q = q.options(db.joinedload(Case.annotation))

    total = q.count()
    cases = q.offset((page - 1) * page_size).limit(page_size).all()
    return jsonify({
        "total": total,
        "page": page,
        "page_size": page_size,
        "cases": [c.to_dict(brief=True) for c in cases],
    }), 200


@cases_bp.route("/<case_id>/annotation", methods=["GET"])
def get_case_annotation(case_id):
    case = Case.query.get(case_id)
    if not case:
        return jsonify({"error": "Case not found"}), 404
    return jsonify({
        "case": case.to_dict(),
        "annotation": case.annotation.to_dict() if case.annotation else None,
    }), 200


@cases_bp.route("/<case_id>", methods=["DELETE"])
def delete_case(case_id):
    case = Case.query.get(case_id)
    if not case:
        return jsonify({"error": "Case not found"}), 404
    if case.annotation:
        db.session.delete(case.annotation)
    db.session.delete(case)
    db.session.commit()
    return jsonify({
        "message": "Case and associated annotations deleted",
        "case_id": case_id,
    }), 200

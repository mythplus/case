from flask import Blueprint, jsonify, request

from app.models import Annotation, Case, db

annotations_bp = Blueprint("annotations", __name__)


def _gen_annotation_id():
    from datetime import datetime

    now = datetime.now()
    count = Annotation.query.filter(
        db.func.date(Annotation.created_at) == now.date()
    ).count() + 1
    return f"a_{now.strftime('%Y%m%d')}_{count:03d}"


@annotations_bp.route("", methods=["POST"])
def create_annotation():
    data = request.get_json(force=True)
    required = ["case_id", "root_cause", "accuracy_score", "operability_score", "readability_score"]
    missing = [f for f in required if f not in data or data[f] is None]
    if missing:
        return jsonify({"error": "Missing required fields", "missing_fields": missing}), 400

    case = Case.query.get(data["case_id"])
    if not case:
        return jsonify({"error": "Case not found"}), 404

    # 乐观锁校验
    client_updated_at = data.get("updated_at")
    if client_updated_at and case.updated_at:
        from datetime import datetime, timezone

        server_ts = case.updated_at.isoformat()
        if client_updated_at != server_ts:
            return jsonify({"error": "Conflict", "message": "Case has been modified by another user"}), 409

    scores = [data["accuracy_score"], data["operability_score"], data["readability_score"]]
    for s in scores:
        if s not in (0, 1, 2):
            return jsonify({"error": "Invalid score value", "message": "Scores must be 0, 1, or 2"}), 400

    overall = round(sum(scores) / 3, 2)

    # 覆盖更新
    existing = Annotation.query.filter_by(case_id=data["case_id"]).first()
    if existing:
        from datetime import datetime, timezone
        existing.root_cause = data["root_cause"]
        existing.accuracy_score = data["accuracy_score"]
        existing.operability_score = data["operability_score"]
        existing.readability_score = data["readability_score"]
        existing.overall_score = overall
        existing.remark = data.get("remark")
        existing.optimization_direction = data.get("optimization_direction")
        case.updated_at = datetime.now()
        db.session.commit()
        return jsonify({
            "annotation_id": existing.annotation_id,
            "overall_score": existing.overall_score,
            "optimization_direction": existing.optimization_direction,
        }), 200

    annotation = Annotation(
        annotation_id=_gen_annotation_id(),
        case_id=data["case_id"],
        root_cause=data["root_cause"],
        accuracy_score=data["accuracy_score"],
        operability_score=data["operability_score"],
        readability_score=data["readability_score"],
        overall_score=overall,
        remark=data.get("remark"),
        optimization_direction=data.get("optimization_direction"),
    )
    db.session.add(annotation)
    case.status = "annotated"
    case.updated_at = datetime.now()
    db.session.commit()
    return jsonify({
        "annotation_id": annotation.annotation_id,
        "overall_score": annotation.overall_score,
        "optimization_direction": annotation.optimization_direction,
    }), 200


@annotations_bp.route("", methods=["GET"])
def list_annotations():
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    category = request.args.get("category")
    case_status = request.args.get("case_status")
    keyword = request.args.get("keyword")
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 20, type=int)

    q = Annotation.query.join(Case)

    if start_date:
        from datetime import datetime
        try:
            start_dt = datetime.fromisoformat(start_date)
            q = q.filter(Annotation.created_at >= start_dt)
        except ValueError:
            pass
    if end_date:
        from datetime import datetime
        try:
            end_dt = datetime.fromisoformat(end_date)
            q = q.filter(Annotation.created_at <= end_dt)
        except ValueError:
            pass
    if category:
        q = q.filter(Case.category == category)
    if case_status:
        q = q.filter(Case.status == case_status)
    if keyword:
        q = q.filter(
            db.or_(
                Case.description.contains(keyword),
                Case.agent_output.contains(keyword),
                Annotation.optimization_direction.contains(keyword),
            )
        )

    # 分数区间筛选
    for dim in ["accuracy", "operability", "readability", "overall"]:
        lo = request.args.get(f"{dim}_min", type=float)
        hi = request.args.get(f"{dim}_max", type=float)
        col = getattr(Annotation, f"{dim}_score", None)
        if col is not None:
            if lo is not None:
                q = q.filter(col >= lo)
            if hi is not None:
                q = q.filter(col <= hi)

    total = q.count()
    items = q.order_by(Annotation.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return jsonify({
        "total": total,
        "page": page,
        "page_size": page_size,
        "annotations": [
            {
                **a.to_dict(),
                "case": {
                    "case_id": a.case.case_id,
                    "category": a.case.category,
                    "description": a.case.description,
                    "status": a.case.status,
                },
            }
            for a in items
        ],
    }), 200


@annotations_bp.route("/<annotation_id>", methods=["DELETE"])
def delete_annotation(annotation_id):
    annotation = Annotation.query.get(annotation_id)
    if not annotation:
        return jsonify({"error": "Annotation not found"}), 404

    case = annotation.case
    db.session.delete(annotation)
    case.status = "pending"
    db.session.commit()
    return jsonify({
        "message": "Annotation deleted, case status reverted to pending",
        "annotation_id": annotation_id,
        "case_id": case.case_id,
        "case_status": case.status,
    }), 200

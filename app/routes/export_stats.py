import csv
import io
import json

from flask import Blueprint, jsonify, request, Response

from app.models import Annotation, Case, db

export_stats_bp = Blueprint("export_stats", __name__)


@export_stats_bp.route("/export", methods=["GET"])
def export_data():
    fmt = request.args.get("format", "csv")
    q = Annotation.query.join(Case)

    # 复用标注查询的筛选逻辑
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    category = request.args.get("category")
    keyword = request.args.get("keyword")
    if start_date:
        q = q.filter(Annotation.created_at >= start_date)
    if end_date:
        q = q.filter(Annotation.created_at <= end_date)
    if category:
        q = q.filter(Case.category == category)
    if keyword:
        q = q.filter(db.or_(Case.description.contains(keyword), Case.agent_output.contains(keyword)))

    for dim in ["accuracy", "operability", "readability", "overall"]:
        lo = request.args.get(f"{dim}_min", type=float)
        hi = request.args.get(f"{dim}_max", type=float)
        col = getattr(Annotation, f"{dim}_score", None)
        if col is not None:
            if lo is not None:
                q = q.filter(col >= lo)
            if hi is not None:
                q = q.filter(col <= hi)

    rows = q.all()

    if fmt == "json":
        data = [
            {"case": a.case.to_dict(), "annotation": a.to_dict()}
            for a in rows
        ]
        return Response(json.dumps(data, ensure_ascii=False, indent=2), mimetype="application/json")

    # CSV with UTF-8 BOM
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow([
        "case_id", "source", "category", "description", "status",
        "run_time_ms", "tokens_consumed", "agent_input", "agent_output",
        "annotation_id", "root_cause", "accuracy_score", "operability_score",
        "readability_score", "overall_score", "remark", "annotated_at",
    ])
    for a in rows:
        c = a.case
        writer.writerow([
            c.case_id, c.source, c.category, c.description, c.status,
            c.run_time_ms, c.tokens_consumed, c.agent_input, c.agent_output,
            a.annotation_id, a.root_cause, a.accuracy_score, a.operability_score,
            a.readability_score, a.overall_score, a.remark,
            a.created_at.isoformat() if a.created_at else "",
        ])
    return Response(output.getvalue(), mimetype="text/csv; charset=utf-8-sig",
                    headers={"Content-Disposition": "attachment; filename=export.csv"})


@export_stats_bp.route("/stats", methods=["GET"])
def stats():
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    category = request.args.get("category")

    q = Case.query
    if start_date:
        q = q.filter(Case.created_at >= start_date)
    if end_date:
        q = q.filter(Case.created_at <= end_date)
    if category:
        q = q.filter(Case.category == category)

    all_cases = q.all()
    annotated = [c for c in all_cases if c.status == "annotated"]
    pending = [c for c in all_cases if c.status == "pending"]

    # 平均分
    ann_scores = [c.annotation for c in annotated if c.annotation]
    averages = {"accuracy": 0, "operability": 0, "readability": 0, "overall": 0}
    if ann_scores:
        for key in averages:
            vals = [getattr(a, f"{key}_score") for a in ann_scores]
            averages[key] = round(sum(vals) / len(vals), 2)

    # 分类分布
    cat_map = {}
    for c in all_cases:
        cat = c.category or "未分类"
        if cat not in cat_map:
            cat_map[cat] = {"annotated": 0, "pending": 0, "scores": []}
        if c.status == "annotated" and c.annotation:
            cat_map[cat]["annotated"] += 1
            cat_map[cat]["scores"].append(c.annotation.overall_score)
        else:
            cat_map[cat]["pending"] += 1

    category_distribution = [
        {
            "category": cat,
            "annotated": v["annotated"],
            "pending": v["pending"],
            "avg_overall": round(sum(v["scores"]) / len(v["scores"]), 2) if v["scores"] else 0,
        }
        for cat, v in cat_map.items()
    ]

    # 低分 Case
    threshold = request.args.get("low_score_threshold", 1.0, type=float)
    low_score = [
        {
            "case_id": c.case_id,
            "category": c.category,
            "overall_score": c.annotation.overall_score,
            "root_cause": c.annotation.root_cause,
        }
        for c in annotated
        if c.annotation and c.annotation.overall_score < threshold
    ]

    return jsonify({
        "overview": {
            "total_cases": len(all_cases),
            "annotated_cases": len(annotated),
            "pending_cases": len(pending),
            "annotation_rate": round(len(annotated) / len(all_cases), 2) if all_cases else 0,
        },
        "averages": averages,
        "category_distribution": category_distribution,
        "low_score_cases": low_score,
    }), 200

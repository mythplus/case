import csv
import io
import json
import os
import threading
import uuid
from datetime import datetime

from flask import Blueprint, jsonify, request, send_file

from app.models import Annotation, Case, db

export_stats_bp = Blueprint("export_stats", __name__)

# 异步导出任务存储 {task_id: {status, format, filename, error}}
_export_tasks = {}
_export_lock = threading.Lock()


def _get_tmp_dir(app):
    """获取临时文件目录，不存在则创建"""
    d = os.path.join(os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "data", "tmp")
    os.makedirs(d, exist_ok=True)
    return d


def _build_query(args):
    """根据请求参数构建查询（复用筛选逻辑）"""
    ids_param = args.get("ids")
    if ids_param:
        ids = [i.strip() for i in ids_param.split(",") if i.strip()]
        return "ids", ids

    q = Annotation.query.join(Case)
    start_date = args.get("start_date")
    end_date = args.get("end_date")
    category = args.get("category")
    keyword = args.get("keyword")
    if start_date:
        try:
            q = q.filter(Annotation.created_at >= datetime.fromisoformat(start_date))
        except ValueError:
            pass
    if end_date:
        try:
            q = q.filter(Annotation.created_at <= datetime.fromisoformat(end_date))
        except ValueError:
            pass
    if category:
        q = q.filter(Case.category == category)
    if keyword:
        # FTS5 trigram 全文搜索：>=3 字符走 MATCH（极快），否则走原始 LIKE 兜底
        if len(keyword) >= 3:
            try:
                fts_ids = [
                    r[0] for r in db.session.execute(
                        db.text("SELECT case_id FROM cases_fts WHERE cases_fts MATCH :kw"),
                        {"kw": keyword},
                    )
                ]
                q = q.filter(Case.case_id.in_(fts_ids))
            except Exception:
                q = q.filter(db.or_(Case.description.contains(keyword), Case.agent_output.contains(keyword)))
        else:
            q = q.filter(db.or_(Case.description.contains(keyword), Case.agent_output.contains(keyword)))

    for dim in ["accuracy", "operability", "readability", "overall"]:
        lo_raw = args.get(f"{dim}_min")
        hi_raw = args.get(f"{dim}_max")
        lo = float(lo_raw) if lo_raw is not None else None
        hi = float(hi_raw) if hi_raw is not None else None
        col = getattr(Annotation, f"{dim}_score", None)
        if col is not None:
            if lo is not None:
                q = q.filter(col >= lo)
            if hi is not None:
                q = q.filter(col <= hi)
    low_score_threshold = args.get("low_score_threshold")
    if low_score_threshold is not None:
        try:
            threshold_val = float(low_score_threshold)
            q = q.filter(Annotation.overall_score == threshold_val)
        except ValueError:
            pass
    return "filter", q


def _generate_file(app, task_id, fmt, args_snapshot):
    """后台线程：生成导出文件"""
    tmp_dir = _get_tmp_dir(app)
    filepath = os.path.join(tmp_dir, f"{task_id}.{fmt}")

    try:
        with app.app_context():
            mode, query_obj = _build_query(args_snapshot)

            if fmt == "json":
                if mode == "ids":
                    cases = Case.query.filter(Case.case_id.in_(query_obj)).all() if query_obj else []
                    data = [
                        {"case": c.to_dict(), "annotation": c.annotation.to_dict() if c.annotation else None}
                        for c in cases
                    ]
                else:
                    rows = query_obj.all()
                    data = [
                        {"case": a.case.to_dict(), "annotation": a.to_dict()}
                        for a in rows
                    ]
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            else:
                # CSV
                output = io.StringIO()
                output.write("\ufeff")
                writer = csv.writer(output)
                writer.writerow([
                    "case_id", "source", "category", "description", "status",
                    "run_time_ms", "tokens_consumed", "agent_input", "agent_output",
                    "created_at", "updated_at",
                    "annotation_id", "root_cause", "accuracy_score", "operability_score",
                    "readability_score", "overall_score", "remark", "optimization_direction", "annotated_at",
                ])
                if mode == "ids":
                    cases = Case.query.filter(Case.case_id.in_(query_obj)).all() if query_obj else []
                    for c in cases:
                        a = c.annotation
                        writer.writerow([
                            c.case_id, c.source, c.category, c.description, c.status,
                            c.run_time_ms, c.tokens_consumed, c.agent_input, c.agent_output,
                            c.created_at.isoformat() if c.created_at else "",
                            c.updated_at.isoformat() if c.updated_at else "",
                            a.annotation_id if a else "", a.root_cause if a else "",
                            a.accuracy_score if a else "", a.operability_score if a else "",
                            a.readability_score if a else "", a.overall_score if a else "",
                            a.remark if a else "",
                            a.optimization_direction if a else "",
                            a.created_at.isoformat() if a and a.created_at else "",
                        ])
                else:
                    rows = query_obj.all()
                    for a in rows:
                        c = a.case
                        writer.writerow([
                            c.case_id, c.source, c.category, c.description, c.status,
                            c.run_time_ms, c.tokens_consumed, c.agent_input, c.agent_output,
                            c.created_at.isoformat() if c.created_at else "",
                            c.updated_at.isoformat() if c.updated_at else "",
                            a.annotation_id, a.root_cause, a.accuracy_score, a.operability_score,
                            a.readability_score, a.overall_score, a.remark, a.optimization_direction,
                            a.created_at.isoformat() if a.created_at else "",
                        ])
                with open(filepath, "w", encoding="utf-8-sig") as f:
                    f.write(output.getvalue())

        with _export_lock:
            _export_tasks[task_id]["status"] = "done"
            _export_tasks[task_id]["filename"] = filepath
    except Exception as e:
        with _export_lock:
            _export_tasks[task_id]["status"] = "failed"
            _export_tasks[task_id]["error"] = str(e)


@export_stats_bp.route("/export", methods=["GET"])
def export_data():
    fmt = request.args.get("format", "csv")
    if fmt not in ("csv", "json"):
        return jsonify({"error": "不支持的格式"}), 400

    task_id = uuid.uuid4().hex[:16]
    # 快照请求参数（避免线程中读取request出错）
    args_snapshot = dict(request.args)

    with _export_lock:
        _export_tasks[task_id] = {"status": "processing", "format": fmt, "filename": None, "error": None}

    from flask import current_app
    app = current_app._get_current_object()
    t = threading.Thread(target=_generate_file, args=(app, task_id, fmt, args_snapshot), daemon=True)
    t.start()

    return jsonify({"task_id": task_id}), 202


@export_stats_bp.route("/export/status/<task_id>", methods=["GET"])
def export_status(task_id):
    with _export_lock:
        task = _export_tasks.get(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404
    resp = {"status": task["status"], "format": task["format"]}
    if task["status"] == "failed":
        resp["error"] = task["error"]
    return jsonify(resp)


@export_stats_bp.route("/export/download/<task_id>", methods=["GET"])
def export_download(task_id):
    with _export_lock:
        task = _export_tasks.get(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404
    if task["status"] != "done":
        return jsonify({"error": "文件未就绪"}), 400

    filepath = task["filename"]
    if not os.path.exists(filepath):
        return jsonify({"error": "文件已过期"}), 404

    fmt = task["format"]
    mimetype = "application/json" if fmt == "json" else "text/csv; charset=utf-8-sig"
    ext = fmt
    download_name = f"export.{ext}"

    return send_file(filepath, mimetype=mimetype, as_attachment=True, download_name=download_name)


@export_stats_bp.route("/stats", methods=["GET"])
def stats():
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    category = request.args.get("category")

    q = Case.query
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            q = q.filter(Case.created_at >= start_dt)
        except ValueError:
            pass
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
            q = q.filter(Case.created_at <= end_dt)
        except ValueError:
            pass
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
        if c.annotation and c.annotation.overall_score == threshold
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

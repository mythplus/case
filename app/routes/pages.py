from flask import Blueprint, render_template, jsonify

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@pages_bp.route("/")
@pages_bp.route("/cases")
def case_list():
    return render_template("cases.html")


@pages_bp.route("/annotate/<case_id>")
def annotate(case_id):
    return render_template("annotate.html", case_id=case_id)


@pages_bp.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@pages_bp.route("/audit-logs")
def audit_logs_page():
    return render_template("audit_logs.html")

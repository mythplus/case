import os
from flask import Flask
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate

from app.models import db


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # 配置
    base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(
        base_dir, "data", "annotation.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
    app.config["BASE_URL"] = os.environ.get("BASE_URL", "http://21.6.116.26:5000")

    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "connect_args": {"check_same_thread": False},
    }

    # 扩展初始化
    db.init_app(app)
    Migrate(app, db)
    CORS(app)
    Limiter(get_remote_address, app=app, default_limits=["60 per minute"])

    # 注册路由
    from app.routes.cases import cases_bp
    from app.routes.annotations import annotations_bp
    from app.routes.export_stats import export_stats_bp
    from app.routes.pages import pages_bp
    from app.routes.webhooks import webhooks_bp

    app.register_blueprint(cases_bp, url_prefix="/api/v1/cases")
    app.register_blueprint(annotations_bp, url_prefix="/api/v1/annotations")
    app.register_blueprint(export_stats_bp, url_prefix="/api/v1")
    app.register_blueprint(webhooks_bp, url_prefix="/api/v1/webhooks")
    app.register_blueprint(pages_bp)

    from app.routes.audit_logs import audit_logs_bp
    app.register_blueprint(audit_logs_bp, url_prefix="/api/v1/audit-logs")

    # 数据库初始化
    with app.app_context():
        os.makedirs(os.path.join(base_dir, "data"), exist_ok=True)
        db.create_all()
        # 启用 SQLite WAL 模式，避免并发写入时 database is locked
        with db.engine.connect() as conn:
            conn.execute(db.text("PRAGMA journal_mode=WAL"))

    return app

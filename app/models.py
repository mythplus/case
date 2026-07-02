from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def _now():
    return datetime.now()


class Case(db.Model):
    __tablename__ = "cases"

    case_id = db.Column(db.String(36), primary_key=True)
    run_time_ms = db.Column(db.Integer, nullable=True)
    tokens_consumed = db.Column(db.Integer, nullable=True)
    source = db.Column(db.Text, nullable=True)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(64), nullable=True)
    use_sliding_window = db.Column(db.Boolean, nullable=True, default=False)
    agent_input = db.Column(db.Text, nullable=False)
    agent_output = db.Column(db.Text, nullable=False)
    detail = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(16), nullable=False, default="pending")
    created_at = db.Column(db.DateTime, nullable=False, default=_now)
    updated_at = db.Column(db.DateTime, nullable=False, default=_now, onupdate=_now)

    annotation = db.relationship("Annotation", backref="case", uselist=False, lazy=True)

    def to_dict(self, brief=False):
        d = {
            "case_id": self.case_id,
            "status": self.status,
            "category": self.category,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if brief:
            d["source"] = self.source
            d["description"] = self.description
            d["use_sliding_window"] = self.use_sliding_window
            d["has_detail"] = bool(self.detail)
            if self.annotation:
                d["accuracy_score"] = self.annotation.accuracy_score
                d["operability_score"] = self.annotation.operability_score
                d["readability_score"] = self.annotation.readability_score
                d["overall_score"] = self.annotation.overall_score
                d["root_cause"] = self.annotation.root_cause
                d["remark"] = self.annotation.remark
                d["optimization_direction"] = self.annotation.optimization_direction
            return d
        d.update(
            {
                "run_time_ms": self.run_time_ms,
                "tokens_consumed": self.tokens_consumed,
                "source": self.source,
                "description": self.description,
                "agent_input": self.agent_input,
                "agent_output": self.agent_output,
                "detail": self.detail,
            }
        )
        return d


class Annotation(db.Model):
    __tablename__ = "annotations"

    annotation_id = db.Column(db.String(36), primary_key=True)
    case_id = db.Column(
        db.String(36), db.ForeignKey("cases.case_id"), nullable=False, unique=True
    )
    root_cause = db.Column(db.Text, nullable=False)
    accuracy_score = db.Column(db.Integer, nullable=False)
    operability_score = db.Column(db.Integer, nullable=False)
    readability_score = db.Column(db.Integer, nullable=False)
    overall_score = db.Column(db.Float, nullable=False)
    remark = db.Column(db.Text, nullable=True)
    optimization_direction = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_now)

    def to_dict(self):
        return {
            "annotation_id": self.annotation_id,
            "case_id": self.case_id,
            "root_cause": self.root_cause,
            "accuracy_score": self.accuracy_score,
            "operability_score": self.operability_score,
            "readability_score": self.readability_score,
            "overall_score": self.overall_score,
            "remark": self.remark,
            "optimization_direction": self.optimization_direction,
            "annotated_at": self.created_at.isoformat() if self.created_at else None,
        }


class WebhookConfig(db.Model):
    __tablename__ = "webhook_configs"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(128), nullable=False, comment="Webhook名称")
    url = db.Column(db.String(512), nullable=False, comment="企微Webhook地址")
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_now)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    action = db.Column(db.String(32), nullable=False, comment="操作类型: create_annotation/update_annotation/delete_annotation/delete_case/delete_webhook/create_webhook/update_webhook")
    target_type = db.Column(db.String(32), nullable=False, comment="目标类型: case/annotation/webhook")
    target_id = db.Column(db.String(128), nullable=True, comment="目标ID")
    detail = db.Column(db.Text, nullable=True, comment="操作详情(JSON)")
    created_at = db.Column(db.DateTime, nullable=False, default=_now)

    def to_dict(self):
        return {
            "id": self.id,
            "action": self.action,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "detail": self.detail,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

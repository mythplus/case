from flask import Blueprint, jsonify, request

from app.models import WebhookConfig, db

webhooks_bp = Blueprint("webhooks", __name__)


@webhooks_bp.route("", methods=["GET"])
def list_webhooks():
    items = WebhookConfig.query.order_by(WebhookConfig.created_at.desc()).all()
    return jsonify({"webhooks": [w.to_dict() for w in items]}), 200


@webhooks_bp.route("", methods=["POST"])
def create_webhook():
    data = request.get_json(force=True)
    name = data.get("name", "").strip()
    url = data.get("url", "").strip()
    if not name or not url:
        return jsonify({"error": "name和url不能为空"}), 400

    wh = WebhookConfig(name=name, url=url, enabled=True)
    db.session.add(wh)
    db.session.commit()
    return jsonify(wh.to_dict()), 200


@webhooks_bp.route("/<int:wh_id>", methods=["PUT"])
def update_webhook(wh_id):
    wh = WebhookConfig.query.get(wh_id)
    if not wh:
        return jsonify({"error": "Webhook不存在"}), 404

    data = request.get_json(force=True)
    if "name" in data:
        wh.name = data["name"].strip() or wh.name
    if "url" in data:
        wh.url = data["url"].strip() or wh.url
    if "enabled" in data:
        wh.enabled = bool(data["enabled"])
    db.session.commit()
    return jsonify(wh.to_dict()), 200


@webhooks_bp.route("/<int:wh_id>", methods=["DELETE"])
def delete_webhook(wh_id):
    wh = WebhookConfig.query.get(wh_id)
    if not wh:
        return jsonify({"error": "Webhook不存在"}), 404
    db.session.delete(wh)
    db.session.commit()
    return jsonify({"message": "已删除"}), 200


@webhooks_bp.route("/test", methods=["POST"])
def test_webhook():
    """测试Webhook连通性，向指定url发送一条测试消息。"""
    data = request.get_json(force=True)
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "url不能为空"}), 400

    import requests as http
    payload = {
        "msgtype": "text",
        "text": {"content": "【标注平台】Webhook连通性测试 ✅"},
    }
    try:
        resp = http.post(url, json=payload, timeout=5)
        result = resp.json()
        if result.get("errcode", 0) == 0:
            return jsonify({"success": True, "message": "测试消息发送成功"}), 200
        else:
            return jsonify({"success": False, "message": result.get("errmsg", "发送失败")}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 200

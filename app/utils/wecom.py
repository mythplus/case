import logging
import threading

import requests

from app.models import WebhookConfig, db

logger = logging.getLogger(__name__)


def _build_markdown_content(case_info):
    """构建企微markdown消息内容。

    case_info: dict, 含 case_id, source, category, annotate_url
    """
    c = case_info
    return (
        f"<font color=\"info\">**[有新 Case 待标注]**</font>\n"
        f"\n"
        f"Case ID: {c['case_id']}\n"
        f"来源: {c['source'] or '未知'}\n"
        f"分类: {c['category'] or '未分类'}\n"
        f"链接: [{c['annotate_url']}]({c['annotate_url']})\n"
        f"[前往标注]({c['annotate_url']})"
    )


def _send_to_webhook(webhook_url, case_info):
    """向单个Webhook地址发送企微通知。"""
    content = _build_markdown_content(case_info)
    payload = {
        "msgtype": "markdown",
        "markdown": {"content": content},
    }
    try:
        resp = requests.post(webhook_url, json=payload, timeout=5)
        if resp.status_code != 200 or resp.json().get("errcode", 0) != 0:
            logger.warning("Webhook发送失败 url=%s status=%s body=%s", webhook_url, resp.status_code, resp.text[:200])
        else:
            logger.info("Webhook发送成功 url=%s", webhook_url)
    except Exception:
        logger.exception("Webhook发送异常 url=%s", webhook_url)


def notify_case(case_info, app):
    """异步通知所有启用的Webhook。

    case_info: dict, 含 case_id, category, description, annotate_url
    app: Flask app 实例（用于app_context）
    """
    def _worker():
        with app.app_context():
            webhooks = WebhookConfig.query.filter_by(enabled=True).all()
            if not webhooks:
                return
            for wh in webhooks:
                _send_to_webhook(wh.url, case_info)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()

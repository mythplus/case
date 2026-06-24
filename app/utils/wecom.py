import logging
import threading

import requests

from app.models import WebhookConfig, db

logger = logging.getLogger(__name__)


def _build_markdown_content(cases_info):
    """构建企微markdown消息内容。

    cases_info: list of dict, 每项含 case_id, source, category, annotate_url
    """
    if len(cases_info) == 1:
        c = cases_info[0]
        return (
            f"<font color=\"info\">**[有新 Case 待标注]**</font>\n"
            f"\n"
            f"Case ID: {c['case_id']}\n"
            f"来源: {c['source'] or '未知'}\n"
            f"分类: {c['category'] or '未分类'}\n"
            f"链接: [{c['annotate_url']}]({c['annotate_url']})\n"
            f"[前往标注]({c['annotate_url']})"
        )

    # 多条 Case 合并
    lines = [f"<font color=\"info\">**[有{len(cases_info)} 条新 Case 待标注]**</font>"]
    for i, c in enumerate(cases_info, 1):
        lines.append(
            f"\n{c['case_id']} | 来源: {c['source'] or '未知'} | 分类: {c['category'] or '未分类'}\n"
            f"[前往标注]({c['annotate_url']})"
        )
    return "\n".join(lines)


def _send_to_webhook(webhook_url, cases_info):
    """向单个Webhook地址发送企微通知。"""
    content = _build_markdown_content(cases_info)
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


def notify_cases(cases_info, app):
    """异步通知所有启用的Webhook。

    cases_info: list of dict, 每项含 case_id, category, description, annotate_url
    app: Flask app 实例（用于app_context）
    """
    def _worker():
        with app.app_context():
            webhooks = WebhookConfig.query.filter_by(enabled=True).all()
            if not webhooks:
                return
            for wh in webhooks:
                _send_to_webhook(wh.url, cases_info)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()

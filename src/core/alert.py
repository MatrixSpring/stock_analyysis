"""告警钩子 — 钉钉 / 企业微信"""

import requests
from src.config.prod_settings import settings
from src.core.prod_logger import api_logger


class AlertClient:
    @staticmethod
    def send_msg(title: str, content: str):
        if not settings.ALERT_ENABLE:
            return
        full_text = f"【StockBackend】{title}\n{content}"
        # 钉钉
        if settings.ALERT_WEBHOOK_DINGDING:
            payload = {"msgtype": "text", "text": {"content": full_text}}
            try:
                requests.post(settings.ALERT_WEBHOOK_DINGDING, json=payload, timeout=5)
            except Exception as e:
                api_logger.warning(f"钉钉告警发送失败 {e}")
        # 企微
        if settings.ALERT_WEBHOOK_WECOM:
            payload = {"msgtype": "text", "text": {"content": full_text}}
            try:
                requests.post(settings.ALERT_WEBHOOK_WECOM, json=payload, timeout=5)
            except Exception as e:
                api_logger.warning(f"企微告警发送失败 {e}")


alert_client = AlertClient()

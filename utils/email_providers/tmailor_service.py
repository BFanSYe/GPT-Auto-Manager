import json
from curl_cffi import requests
from utils import config as cfg

class TmailorService:
    def __init__(self, current_token: str, proxies: dict = None):
        self.current_token = current_token.strip() if current_token else ""
        self.proxies = proxies
        self.session = requests.Session(impersonate="chrome120")

        if self.proxies:
            if isinstance(self.proxies, dict):
                self.session.proxies = self.proxies
            else:
                self.session.proxies = {"http": self.proxies, "https": self.proxies}

        self.url_api = "https://tmailor.com/api"
        self.headers = {
            'origin': 'https://tmailor.com',
            'referer': 'https://tmailor.com/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36'
        }

    def create_email(self):
        """生成新邮箱"""
        payload = {
            'action': 'newemail',
            'curentToken': self.current_token,
            'fbToken': None,
        }
        try:
            res = self.session.post(self.url_api, headers=self.headers, json=payload, timeout=15)
            if res.status_code == 200:
                data = res.json()
                return data.get('email'), data.get('accesstoken')
        except Exception as e:
            print(f"[{cfg.ts()}] [ERROR] Tmailor 创建邮箱请求异常: {e}")
        return None, None

    def get_inbox(self, access_token: str) -> dict:
        """获取收件箱列表"""
        payload = {
            "action": "listinbox",
            "accesstoken": access_token,
            "curentToken": self.current_token,
            "fbToken": None
        }
        try:
            res = self.session.post(self.url_api, headers=self.headers, json=payload, timeout=15)
            if res.status_code == 200:
                return res.json().get("data", {})
        except Exception as e:
            print(f"[{cfg.ts()}] [ERROR] Tmailor 获取列表异常: {e}")
        return {}

    def read_email(self, access_token: str, target_uuid: str, target_email_id: str):
        """读取邮件真实正文"""
        payload = {
            "action": "read",
            "accesstoken": access_token,
            "curentToken": self.current_token,
            "email_code": target_uuid,
            "email_token": target_email_id,
            "fbToken": None
        }
        try:
            res = self.session.post(self.url_api, headers=self.headers, json=payload, timeout=15)
            if res.status_code == 200:
                data = res.json().get("data", {})
                if data:
                    return data.get("body", ""), data.get("subject", "")
        except Exception as e:
            print(f"[{cfg.ts()}] [ERROR] Tmailor 读取邮件异常: {e}")
        return "", ""
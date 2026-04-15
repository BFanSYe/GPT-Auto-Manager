import json
from curl_cffi import requests
from utils import config as cfg

class InboxesService:
    def __init__(self, proxies: dict = None):
        self.session = requests.Session(impersonate="chrome120")
        if proxies:
            self.session.proxies = proxies if isinstance(proxies, dict) else {"http": proxies, "https": proxies}
        self.base_url = "https://inboxes.com/api/v2"
        self.headers = {
            'accept': 'application/json, text/plain, */*',
            'origin': 'https://inboxes.com',
            'referer': 'https://inboxes.com/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36'
        }

    def create_email(self):
        url = f"{self.base_url}/inbox"
        try:
            res = self.session.post(url, headers=self.headers, json={}, timeout=15)
            if res.status_code == 200:
                data = res.json()
                email = data.get("inbox")
                user_id = self.session.cookies.get_dict().get("user_id")
                if email and user_id:
                    return email, user_id
        except Exception as e:
            print(f"[{cfg.ts()}] [ERROR] Inboxes.com 获取邮箱异常: {e}")
        return None, None

    def get_inbox(self, email_address: str, user_id: str):
        url = f"{self.base_url}/inbox/{email_address}"
        cookies = {"user_id": user_id}
        try:
            res = self.session.get(url, headers=self.headers, cookies=cookies, timeout=10)
            if res.status_code == 200:
                return res.json().get("msgs", [])
        except Exception:
            pass
        return []
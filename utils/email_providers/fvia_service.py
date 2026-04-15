import random
import string
from curl_cffi import requests

class FviaMailService:
    def __init__(self, token: str, proxies: dict = None):
        self.token = token.strip()
        self.session = requests.Session(impersonate="chrome120")
        if proxies:
            self.session.proxies = proxies if isinstance(proxies, dict) else {"http": proxies, "https": proxies}
        self.base_url = "https://fviainboxes.com"
        self.headers = {
            'accept': 'application/json, text/plain, */*',
            'referer': 'https://fviainboxes.com/',
            'authorization': f'Bearer {self.token}',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/146.0.0.0 Safari/537.36'
        }

    def create_email(self):
        """获取域名列表并随机生成全套地址"""
        try:
            res = self.session.get(f"{self.base_url}/domains", timeout=15)
            if res.status_code == 200:
                domains = res.json().get("result", [])
                if domains:
                    domain = random.choice(domains)
                    username = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
                    return f"{username}@{domain}", self.token
        except Exception as e:
            print(f"Fvia 获取域名异常: {e}")
        return None, None

    def get_inbox(self, email_address: str):
        """拉取邮件列表"""
        user, dom = email_address.split("@")
        url = f"{self.base_url}/messages?username={user}&domain={dom}"
        try:
            res = self.session.get(url, headers=self.headers, timeout=10)
            return res.json().get("result", []) if res.status_code == 200 else []
        except:
            return []
import random
import string
from curl_cffi import requests
from utils import config as cfg

class TemporaryMailService:
    def __init__(self, proxies: dict = None):
        self.session = requests.Session(impersonate="chrome120")
        if proxies:
            self.session.proxies = proxies if isinstance(proxies, dict) else {"http": proxies, "https": proxies}
        self.base_url = "https://temporarymail.com/api/"
        self.headers = {
            'accept': '*/*',
            'referer': 'https://temporarymail.com/en/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
            'x-requested-with': 'XMLHttpRequest'
        }

    def create_email(self):
        """申请邮箱并获取 secretKey"""
        # 免费域名池
        free_domains = [
            "AllFreeMail.net",
            "AllWebEmails.com",
            "EasyMailer.live",
            "HorizonsPost.com",
            "InboxOrigin.com",
            "MailMagnet.co",
            "MyCreativeInbox.com",
            "OpenMail.pro",
            "SolarNyx.com"
        ]
        username = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
        domain = random.choice(free_domains)
        email_address = f"{username}@{domain}"
        url = f"{self.base_url}?action=requestEmailAccess&key=&value={email_address}"

        try:
            res = self.session.get(url, headers=self.headers, timeout=15)
            if res.status_code == 200:
                data = res.json()
                secret_key = data.get("secretKey")
                if secret_key:
                    return email_address, secret_key
        except Exception as e:
            print(f"[{cfg.ts()}] [ERROR] TemporaryMail 申请异常: {e}")
        return None, None

    def get_inbox_list(self, secret_key: str):
        """获取邮件列表"""
        url = f"{self.base_url}?action=checkInbox&value={secret_key}"
        try:
            res = self.session.get(url, headers=self.headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                return data if isinstance(data, dict) else {}
        except:
            pass
        return {}

    def get_email_detail(self, mail_id: str):
        """解密阅读真实正文和标题"""
        url = f"{self.base_url}?action=getEmail&value={mail_id}"
        try:
            res = self.session.post(url, headers=self.headers, data="", timeout=10)
            if res.status_code == 200:
                data = res.json()
                return data.get(mail_id, {})
        except:
            pass
        return {}
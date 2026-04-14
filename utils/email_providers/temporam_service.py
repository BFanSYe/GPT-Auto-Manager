import random
import uuid
import threading
from curl_cffi import requests
from utils import config as cfg

TEMPORAM_URL = "https://www.temporam.com/zh"
API_MESSAGES = "https://www.temporam.com/api/emails?email={email}"
API_DOMAINS = "https://www.temporam.com/api/domains"

_cached_domains = []
_domains_lock = threading.Lock()

class TemporamService:
    def __init__(self, proxies=None):
        self.proxies = proxies
        self.req_proxies = None
        if proxies:
            if isinstance(proxies, dict):
                self.req_proxies = proxies
            else:
                self.req_proxies = {"http": str(proxies), "https": str(proxies)}

    def _get_cookies_dict(self) -> dict:
        raw_cookie = getattr(cfg, 'TEMPORAM_COOKIE', '')
        cookie_dict = {}
        if raw_cookie:
            for item in raw_cookie.split(';'):
                if '=' in item:
                    k, v = item.split('=', 1)
                    cookie_dict[k.strip()] = v.strip()
        return cookie_dict

    def _get_available_domains(self) -> list:
        global _cached_domains
        with _domains_lock:
            if _cached_domains:
                return _cached_domains

            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": TEMPORAM_URL,
                "Accept": "application/json"
            }
            try:
                resp = requests.get(
                    API_DOMAINS,
                    headers=headers,
                    proxies=self.req_proxies,
                    impersonate="chrome110",
                    timeout=10
                )
                if resp.status_code == 200:
                    data = resp.json().get("data", [])
                    _cached_domains = [item.get("domain") for item in data if item.get("domain") and item.get("domain") != "mona.edu.rs"]
            except Exception as e:
                print(f"[{cfg.ts()}] [ERROR] 动态获取 Temporam 域名列表失败: {e}")
            if not _cached_domains:
                _cached_domains = ["nooboy.com", "temporam.com", "tianmi.me", "temporam.shop"]

            return _cached_domains

    def create_email(self) -> tuple:
        try:
            if not getattr(cfg, 'TEMPORAM_COOKIE', ''):
                print(f"[{cfg.ts()}] [ERROR] 未配置 Temporam Cookie，请前往前端网页填入！")
                return None, None

            username = uuid.uuid4().hex[:10]
            domains = self._get_available_domains()
            domain = random.choice(domains)
            email = f"{username}@{domain}"

            return email, email
        except Exception as e:
            print(f"[{cfg.ts()}] [ERROR] 创建 Temporam 邮箱异常: {e}")
            return None, None

    def get_messages(self, email: str) -> list:
        cookies = self._get_cookies_dict()
        if not cookies:
            print(f"[{cfg.ts()}] [DEBUG] Temporam Cookie 解析结果为空！请检查前端是否成功传值。")
            return []
        url = API_MESSAGES.format(email=requests.utils.quote(email))
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": TEMPORAM_URL,
            "Accept": "application/json"
        }
        try:
            resp = requests.get(
                url,
                cookies=cookies,
                headers=headers,
                proxies=self.req_proxies,
                impersonate="chrome110",
                timeout=10
            )
            if resp.status_code == 200:
                try:
                    return resp.json()
                except Exception as e:
                    print(f"[{cfg.ts()}] [ERROR] Temporam JSON 解析失败: {e}，返回的可能不是标准JSON。")
                    return []
            elif resp.status_code in [401, 403]:
                print(f"[{cfg.ts()}] [WARNING] Temporam Cookie 已过期或被拒绝(HTTP {resp.status_code})，请前往面板重新获取并保存。")
            return []

        except Exception as e:
            if "timeout" not in str(e).lower():
                print(f"[{cfg.ts()}] [ERROR] Temporam API 网络请求异常: {e}")
            return []
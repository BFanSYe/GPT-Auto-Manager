import re
import time
from curl_cffi import requests
from utils import config as cfg


class GeneratorEmailService:
    def __init__(self, proxies=None):
        self.proxies = proxies
        self.base_url = "https://generator.email"
        self.timeout = 30
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }

    def _request_with_retry(self, url: str, *, cookies=None, retries: int = 3):
        last_error = None
        for attempt in range(1, retries + 1):
            try:
                resp = requests.get(
                    url,
                    headers=self.headers,
                    cookies=cookies,
                    proxies=self.proxies,
                    timeout=self.timeout,
                    impersonate="chrome110"
                )
                if resp.status_code == 200:
                    return resp
                print(f"[{cfg.ts()}] [WARNING] GeneratorEmail 请求异常 (HTTP {resp.status_code})，重试 {attempt}/{retries}")
            except Exception as e:
                last_error = e
                print(f"[{cfg.ts()}] [WARNING] GeneratorEmail 网络异常，重试 {attempt}/{retries}: {e}")
            if attempt < retries:
                time.sleep(min(2 * attempt, 5))
        if last_error:
            raise last_error
        return None

    def _parse_email(self, html: str) -> str:
        if not html: return None

        match = re.search(r'id="email_ch_text"[^>]*>([^<]+)</span>', html, re.I)
        if not match:
            match = re.search(r'id="email_ch_text"[^>]*>([^<]+)<', html, re.I)
        if match:
            return match.group(1).strip()

        user_match = re.search(r'id="userName"[^>]*value="([^"]+)"', html, re.I)
        domain_match = re.search(r'id="domainName2"[^>]*value="([^"]+)"', html, re.I)
        if user_match and domain_match:
            return f"{user_match.group(1).strip()}@{domain_match.group(1).strip()}"

        return None

    def _build_surl(self, email: str) -> str:
        if not email or "@" not in email:
            return None
        username, domain = email.split("@", 1)
        safe_user = re.sub(r"[^a-zA-Z_0-9.-]", "", username).lower()
        return f"{domain.lower()}/{safe_user}"

    def create_email(self) -> tuple:
        try:
            resp = self._request_with_retry(self.base_url)
            if resp.status_code == 200:
                email = self._parse_email(resp.text)
                if email:
                    surl = self._build_surl(email)
                    return email, surl

            if resp is not None:
                print(f"[{cfg.ts()}] [ERROR] GeneratorEmail 获取页面失败 (HTTP {resp.status_code})")
        except Exception as e:
            print(f"[{cfg.ts()}] [ERROR] GeneratorEmail 创建异常: {e}")
        return None, None

    def get_verification_code(self, surl: str) -> str:
        if not surl:
            return ""

        mailbox_url = f"{self.base_url}/{surl}"
        cookies = {"surl": surl}

        try:
            resp = self._request_with_retry(mailbox_url, cookies=cookies, retries=2)
            if resp.status_code == 200:
                html = resp.text or ""
                direct = re.findall(r"Your ChatGPT code is (\d{6})", html, re.I)
                if direct: return direct[-1]

                contextual = re.findall(r"(?:openai|chatgpt)[\s\S]{0,200}?(\d{6})", html, re.I)
                if contextual: return contextual[-1]
                if "openai" in html.lower() or "chatgpt" in html.lower():
                    generic = re.findall(r"\b(\d{6})\b", html)
                    if generic: return generic[-1]

        except Exception as e:
            pass
        return ""

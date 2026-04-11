import re
import sys
import time
import random
import threading
from pathlib import Path
from curl_cffi import requests
from typing import Optional, Any
from utils import config as cfg

_LUCKMAIL_CLIENT_CLASS_CACHE = None
_LUCKMAIL_API_LOCK = threading.Lock()
_LUCKMAIL_LAST_REQ_TIME = 0.0
_LUCKMAIL_REQ_INTERVAL = 2.0

def _load_luckmail_client_class():
    global _LUCKMAIL_CLIENT_CLASS_CACHE
    if _LUCKMAIL_CLIENT_CLASS_CACHE is not None:
        return _LUCKMAIL_CLIENT_CLASS_CACHE

    try:
        from luckmail import LuckMailClient
        _LUCKMAIL_CLIENT_CLASS_CACHE = LuckMailClient
        return _LUCKMAIL_CLIENT_CLASS_CACHE
    except ImportError:
        pass

    candidates = [
        Path(__file__).resolve().parent / "luckmail",
        Path(__file__).resolve().parents[1] / "tools" / "luckmail",
    ]
    for path in candidates:
        if not path.is_dir(): continue
        if str(path) not in sys.path: sys.path.insert(0, str(path))
        try:
            from luckmail import LuckMailClient
            _LUCKMAIL_CLIENT_CLASS_CACHE = LuckMailClient
            return _LUCKMAIL_CLIENT_CLASS_CACHE
        except Exception:
            continue

    return None

class LuckMailService:
    """直连版 LuckMail 接码服务"""
    
    def __init__(self, api_key: str, preferred_domain: str = "", proxies: dict = None, email_type: str = "ms_graph", variant_mode: str = ""):
        if not api_key:
            raise ValueError("LuckMail API_KEY 不能为空！请检查配置。")

        self.api_key = api_key
        self.base_url = "https://mails.luckyous.com"
        self.project_code = "openai"
        self.preferred_domain = preferred_domain.strip()
        self.proxies = proxies

        # 保存邮箱类型和变种模式
        self.email_type = email_type.strip() or "ms_graph"
        self.variant_mode = variant_mode.strip()

        client_cls = _load_luckmail_client_class()
        if not client_cls:
            raise ValueError("未找到 LuckMail SDK！请确保本地存在 luckmail 文件夹。")

        self.client = client_cls(base_url=self.base_url + "/", api_key=self.api_key)

        if self.proxies and hasattr(self.client, "session"):
            self.client.session.proxies = self.proxies

    def _extract_field(self, obj: any, *keys: str) -> any:
        if not obj: return None
        if isinstance(obj, dict):
            for k in keys:
                if k in obj: return obj.get(k)
        for k in keys:
            if hasattr(obj, k): return getattr(obj, k)
        return None

    def get_email_and_token(self, auto_tag: bool = False, tag_id: int = None) -> tuple:
        api_url = f"{self.base_url}/api/v1/openapi/email/purchase"
        headers = {"X-API-Key": self.api_key, "Content-Type": "application/json"}
        payload = {"project_code": self.project_code, "email_type": self.email_type, "quantity": 1}
        if self.preferred_domain: payload["domain"] = self.preferred_domain
        if self.email_type == "google_variant" and self.variant_mode: payload["variant_mode"] = self.variant_mode

        max_retries = 5
        global _LUCKMAIL_LAST_REQ_TIME

        for attempt in range(max_retries):
            try:
                with _LUCKMAIL_API_LOCK:
                    now = time.time()
                    elapsed = now - _LUCKMAIL_LAST_REQ_TIME
                    if elapsed < _LUCKMAIL_REQ_INTERVAL:

                        time.sleep(_LUCKMAIL_REQ_INTERVAL - elapsed)
                    _LUCKMAIL_LAST_REQ_TIME = time.time()

                resp = requests.post(
                    api_url,
                    headers=headers,
                    json=payload,
                    timeout=30,
                    impersonate="chrome110"
                )

                if resp.status_code in [429, 502, 503, 504]:
                    print(f"[{cfg.ts()}] [LuckMail] 网关限流 ({resp.status_code})，正在进行第 {attempt + 1} 次重试...")
                    time.sleep(2 * (attempt + 1))
                    continue

                res_data = resp.json()

                if res_data.get("code") != 0:
                    msg = res_data.get("message", resp.text)

                    if "频繁" in msg or "稍后重试" in msg or "limit" in msg.lower():
                        print(f"[{cfg.ts()}] [LuckMail] 触发业务限频: {msg}，正在退避排队...")
                        time.sleep(3)
                        continue
                    else:
                        raise Exception(msg)

                data_field = res_data.get("data", {})
                item = data_field.get("purchases", [{}])[0] if "purchases" in data_field else data_field
                email = str(self._extract_field(item, "email_address") or "").strip().lower()
                token = str(self._extract_field(item, "token") or "").strip()
                p_id = self._extract_field(item, "id")

                if p_id and auto_tag and tag_id:
                    self.set_email_tag(p_id, tag_id)
                return email, token, p_id

            except Exception as e:
                if attempt == max_retries - 1:
                    raise Exception(f"LuckMail 购号异常 (已重试{max_retries}次): {e}")
                time.sleep(1.5)

    def get_imported_email_and_order(self, specified_email: str = "") -> tuple:
        """从 LuckMail 私有邮箱池创建接码订单。

        与 purchase 模式不同，这里走的是 /order/create，
        适用于“用户先在 LuckMail 后台/API 导入邮箱，再由本项目消费”的场景。
        返回值第二项不是 token，而是 order_no。
        """
        api_url = f"{self.base_url}/api/v1/openapi/order/create"
        headers = {"X-API-Key": self.api_key, "Content-Type": "application/json"}
        payload = {"project_code": self.project_code}
        if self.email_type:
            payload["email_type"] = self.email_type
        if self.preferred_domain:
            payload["domain"] = self.preferred_domain
        if specified_email:
            payload["specified_email"] = specified_email.strip().lower()
        if self.email_type == "google_variant" and self.variant_mode:
            payload["variant_mode"] = self.variant_mode

        last_error = None
        for attempt in range(1, 4):
            try:
                resp = requests.post(
                    api_url,
                    headers=headers,
                    json=payload,
                    proxies=self.proxies,
                    timeout=30,
                    impersonate="chrome110"
                )
                if resp.status_code in [429, 502, 503, 504]:
                    print(f"[{cfg.ts()}] [LuckMail] 私有池下单网关异常 ({resp.status_code})，重试 {attempt}/3...")
                    time.sleep(2 * attempt)
                    continue

                res_data = resp.json()
                if res_data.get("code") != 0:
                    raise Exception(res_data.get("message") or resp.text)

                data = res_data.get("data", {}) or {}
                email = str(data.get("email_address") or "").strip().lower()
                order_no = str(data.get("order_no") or "").strip()
                return email, order_no
            except Exception as e:
                last_error = e
                if attempt < 3:
                    time.sleep(1.5 * attempt)
        raise Exception(f"LuckMail 私有池下单失败: {last_error}")

    def get_order_code(self, order_no: str) -> str:
        """按订单号查询验证码，配合 imported pool 模式使用。"""
        if not order_no:
            return ""

        api_url = f"{self.base_url}/api/v1/openapi/order/{order_no}/code"
        headers = {"X-API-Key": self.api_key}

        try:
            resp = requests.get(
                api_url,
                headers=headers,
                proxies=self.proxies,
                timeout=30,
                impersonate="chrome110"
            )
            res_data = resp.json()
            if res_data.get("code") != 0:
                return ""

            data = res_data.get("data", {}) or {}
            if str(data.get("status") or "").strip().lower() != "success":
                return ""

            code = str(data.get("verification_code") or "").strip()
            if code:
                match = re.search(r'\b\d{6}\b', code)
                if match:
                    return match.group(0)
            return ""
        except Exception:
            return ""

    def bulk_purchase(self, quantity: int = 1, auto_tag: bool = False, tag_id: int = None) -> list:
        api_url = f"{self.base_url}/api/v1/openapi/email/purchase"
        headers = {"X-API-Key": self.api_key, "Content-Type": "application/json"}
        payload = {"project_code": self.project_code, "email_type": self.email_type, "quantity": quantity}

        if self.preferred_domain: payload["domain"] = self.preferred_domain
        if self.email_type == "google_variant" and self.variant_mode: payload["variant_mode"] = self.variant_mode

        try:
            resp = requests.post(api_url, headers=headers, json=payload, timeout=60)
            res_data = resp.json()
            if res_data.get("code") != 0: raise Exception(res_data.get("message"))

            items = res_data.get("data", {}).get("purchases", [])
            results = []
            for item in items:
                email = str(self._extract_field(item, "email_address") or "").strip().lower()
                token = str(self._extract_field(item, "token") or "").strip()
                purchase_id = self._extract_field(item, "id")

                if purchase_id and auto_tag and tag_id:
                    self.set_email_tag(purchase_id, tag_id)

                results.append({"email": email, "token": token})
            return results
        except Exception as e:
            raise Exception(f"LuckMail 批量购买失败: {e}")

    def get_code(self, token: str) -> str:
        result = self.client.user.get_token_code(token)
        code = str(self._extract_field(result, "verification_code") or "").strip()
        
        if code:
            match = re.search(r'\b\d{6}\b', code)
            if match:
                return match.group(0)
        return ""

    def get_purchased_emails(self, page=1, page_size=100, **kwargs) -> list:
        api_url = f"{self.base_url}/api/v1/openapi/email/purchases"
        headers = {"X-API-Key": self.api_key}
        params = {"page": page, "page_size": page_size, "user_disabled": 0}
        params.update({k: v for k, v in kwargs.items() if v is not None})
        try:
            resp = requests.get(api_url, headers=headers, params=params, proxies=self.proxies, timeout=60,
                                impersonate="chrome110")
            res_data = resp.json()
            return res_data.get("data", {}).get("list", []) if res_data.get("code") == 0 else []
        except Exception as e:
            print(f"[{cfg.ts()}] [WARNING] 获取 LuckMail 列表超时或失败: {e}")
            return []

    def get_random_purchased_email(self, tag_id: int, local_used_pids: set = None) -> tuple:
        import random
        keyword = self.preferred_domain if self.preferred_domain else None
        available_emails = []
        for page in range(1, 4):
            emails = self.get_purchased_emails(page=page, page_size=100, keyword=keyword)
            if not emails:
                break

            for e in emails:
                p_id = self._extract_field(e, "id")
                remote_tag = str(e.get("tag_id"))
                if remote_tag != str(tag_id) and (not local_used_pids or p_id not in local_used_pids):
                    available_emails.append(e)

            if available_emails:
                break

        if not available_emails:
            return None, None, None

        item = random.choice(available_emails)
        email = str(self._extract_field(item, "email_address") or "").strip().lower()
        token = str(self._extract_field(item, "token") or "").strip()
        p_id = self._extract_field(item, "id")
        return email, token, p_id

    def set_email_tag(self, purchase_id: int, tag_id: int) -> bool:
        if not tag_id: return False
        api_url = f"{self.base_url}/api/v1/openapi/email/purchases/{purchase_id}/tag"
        try:
            resp = requests.put(api_url, headers={"X-API-Key": self.api_key}, json={"tag_id": tag_id}, timeout=60)
            return resp.status_code == 200
        except Exception:
            return False

    def create_tag(self, name: str = "已使用") -> Optional[int]:
        api_url = f"{self.base_url}/api/v1/openapi/email/tags"
        headers = {"X-API-Key": self.api_key, "Content-Type": "application/json"}
        payload = {"name": name, "remark": "自动创建", "limit_type": 1}
        try:
            resp = requests.post(api_url, headers=headers, json=payload, timeout=10)
            res_data = resp.json()
            return res_data.get("data", {}).get("id") if res_data.get("code") == 0 else None
        except Exception:
            return None

    def get_tags(self) -> list:
        api_url = f"{self.base_url}/api/v1/openapi/email/tags"
        headers = {"X-API-Key": self.api_key}
        try:
            resp = requests.get(api_url, headers=headers, proxies=self.proxies, timeout=60, impersonate="chrome110")
            res_data = resp.json()
            return res_data.get("data", []) if res_data.get("code") == 0 else []
        except Exception:
            return []

    def ensure_tag_id(self, tag_name: str = "已使用") -> Optional[int]:
        tags = self.get_tags()
        for t in tags:
            if t.get("name") == tag_name:
                return t.get("id")

    def get_or_create_tag_id(self, tag_name: str = "已使用") -> Optional[int]:
        tags = self.get_tags()
        for t in tags:
            if t.get("name") == tag_name:
                return t.get("id")
        print(f"[{cfg.ts()}] [LuckMail] 未找到 '{tag_name}'，正在自动创建...")
        return self.create_tag(tag_name)

    def check_token_alive(self, token: str) -> bool:
        if not token:
            return False

        api_url = f"{self.base_url}/api/v1/openapi/email/token/{token}/alive"
        headers = {"X-API-Key": self.api_key}

        try:
            resp = requests.get(
                api_url,
                headers=headers,
                proxies=self.proxies,
                timeout=30,
                impersonate="chrome110"
            )
            res_data = resp.json()

            if res_data.get("code") == 0:
                is_alive = res_data.get("data", {}).get("alive", False)
                status_msg = res_data.get("data", {}).get("message", "")
                if not is_alive:
                    print(f"[{cfg.ts()}] [LuckMail] 邮箱Token失效原因: {status_msg}")
                return is_alive
            return False
        except Exception as e:
            print(f"[{cfg.ts()}] [LuckMail] 检查邮箱可用性请求异常: {e}")
            return False

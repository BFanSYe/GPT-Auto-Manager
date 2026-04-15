import os
import queue
import threading
import yaml
import random
import string
import shutil
from datetime import datetime
from typing import Optional
from utils.proxy_manager import reload_proxy_config

CONFIG_FILE_LOCK = threading.Lock()
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_DIR)
CONFIG_PATH = os.path.join(BASE_DIR, "data", "config.yaml")
def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")

def format_docker_url(url: str) -> str:
    if not url or not isinstance(url, str):
        return url
    if os.path.exists("/.dockerenv"):
        url = url.replace("127.0.0.1", "host.docker.internal")
        url = url.replace("localhost", "host.docker.internal")
    return url

def normalize_proxy_url(url: str) -> str:
    if not url or not isinstance(url, str):
        return ""
    url = url.strip()
    if not url:
        return ""
    if "://" not in url:
        url = f"http://{url}"
    return format_docker_url(url)

def deep_update_config(default_dict, user_dict):
    """
    递归检查配置文件
    """
    updated = False
    for key, value in default_dict.items():
        if key not in user_dict:
            user_dict[key] = value
            updated = True
        elif isinstance(value, dict) and isinstance(user_dict[key], dict):
            if deep_update_config(value, user_dict[key]):
                updated = True
    return updated

def init_config():
    # 配置文件路径放到data 目录下
    config_dir = os.path.join(BASE_DIR, "data")
    config_path = os.path.join(config_dir, "config.yaml")
    template_path = os.path.join(BASE_DIR, "config.example.yaml")

    os.makedirs(config_dir, exist_ok=True)
    if not os.path.exists(config_path):
        if os.path.exists(template_path):
            print(f"[{ts()}] [系统] 未检测到 {config_path}，正在从模板自动生成...")
            try:
                shutil.copyfile(template_path, config_path)
                print(f"[{ts()}] [SUCCESS] 配置文件初始化成功！程序已加载默认配置。")
            except PermissionError:
                print(f"[{ts()}] [ERROR] 权限不足，无法在 {config_dir} 目录创建配置。请检查 Docker 目录权限。")
                exit(1)
            except Exception as e:
                print(f"[{ts()}] [ERROR] 自动生成配置文件失败: {e}")
                exit(1)
        else:
            print(f"[{ts()}] [ERROR] 缺少核心模板文件 {template_path}，无法启动！")
            exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        user_config = yaml.safe_load(f) or {}
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            default_config = yaml.safe_load(f) or {}

        if deep_update_config(default_config, user_config):
            print(f"[{ts()}] [系统] 🛠️ 检测到旧版配置缺失新参数，已自动补齐并生效！")
            try:
                with CONFIG_FILE_LOCK:
                    with open(config_path, "w", encoding="utf-8") as f:
                        yaml.dump(user_config, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
            except Exception as e:
                print(f"[{ts()}] [WARNING] 自动补全配置文件写入失败: {e}")

    return user_config

# 运行时全局配置缓存。所有 Web 保存动作最终都会回写 data/config.yaml，再由这里热加载到内存。
_c: dict = {}
ENABLE_SUB_DOMAINS: bool = False
SUB_DOMAIN_COUNT: int = 10
EMAIL_API_MODE: str = ""
MAIL_DOMAINS: str = ""
GPTMAIL_BASE: str = ""
ADMIN_AUTH: str = ""

IMAP_SERVER: str = ""
IMAP_PORT: int = 993
IMAP_USER: str = ""
IMAP_PASS: str = ""

LOCAL_MS_ENABLE_FISSION: bool = False
LOCAL_MS_POOL_FISSION: bool = False
LOCAL_MS_MASTER_EMAIL: str = ""
LOCAL_MS_CLIENT_ID: str = ""
LOCAL_MS_REFRESH_TOKEN: str = ""

FREEMAIL_API_URL: str = ""
FREEMAIL_API_TOKEN: str = ""

CM_API_URL: str = ""
CM_ADMIN_EMAIL: str = ""
CM_ADMIN_PASS: str = ""

MC_API_BASE: str = ""
MC_KEY: str = ""

DEFAULT_PROXY: str = ""
# HTTP 动态代理池：用于“动态 HTTP 网关”类型代理服务商。
# 当 enable=true 时，系统会把 proxy_list 或 default_proxy 装入 PROXY_QUEUE，
# 由多线程注册逻辑逐个领取通道，而不是走 Clash/Mihomo API 切点。
# 如果只提供一条动态代理，会按 pool_size 复制成多个并发工作位；
# 是否换 IP 取决于服务商是否按“新建连接/会话”轮换出口。
HTTP_DYNAMIC_PROXY_ENABLE: bool = False
HTTP_DYNAMIC_PROXY_POOL_SIZE: int = 0
HTTP_DYNAMIC_PROXY_LIST: list = []

ENABLE_MULTI_THREAD_REG: bool = False
REG_THREADS: int = 3
MAX_OTP_RETRIES: int = 5
USE_PROXY_FOR_EMAIL: bool = False
ENABLE_EMAIL_MASKING: bool = True

LOGIN_DELAY_MIN: int = 20
LOGIN_DELAY_MAX: int = 45

ENABLE_CPA_MODE: bool = False
SAVE_TO_LOCAL_IN_CPA_MODE: bool = True
CPA_API_URL: str = ""
CPA_API_TOKEN: str = ""
MIN_ACCOUNTS_THRESHOLD: int = 30
BATCH_REG_COUNT: int = 1
MIN_REMAINING_WEEKLY_PERCENT: int = 80
REMOVE_ON_LIMIT_REACHED: bool = False
REMOVE_DEAD_ACCOUNTS: bool = False
CPA_THREADS: int = 10
CPA_AUTO_CHECK: bool = True
CHECK_INTERVAL_MINUTES: int = 60
ENABLE_TOKEN_REVIVE: bool = False
SUB_DOMAIN_LEVEL: int = 1
RANDOM_SUB_DOMAIN_LEVEL: bool = False
ENABLE_SUB2API_MODE: bool = False
SUB2API_URL: str = ""
SUB2API_KEY: str = ""
SUB2API_MIN_THRESHOLD: int = 70
SUB2API_BATCH_COUNT: int = 2
SUB2API_CHECK_INTERVAL: int = 60
SUB2API_THREADS: int = 10
SUB2API_SAVE_TO_LOCAL: bool = True
SUB2API_REMOVE_ON_LIMIT_REACHED: bool = True
SUB2API_REMOVE_DEAD_ACCOUNTS: bool = True
SUB2API_ENABLE_TOKEN_REVIVE: bool = False
SUB2API_AUTO_CHECK: bool = True
SUB2API_ACCOUNT_CONCURRENCY: int = 10
SUB2API_ACCOUNT_LOAD_FACTOR: int = 10
SUB2API_ACCOUNT_PRIORITY: int = 1
SUB2API_ACCOUNT_RATE_MULTIPLIER: float = 1.0
SUB2API_ACCOUNT_GROUP_IDS: list = []
SUB2API_ENABLE_WS_MODE: bool = True

LUCKMAIL_PREFERRED_DOMAIN: str = ""
LUCKMAIL_EMAIL_TYPE: str = ""
LUCKMAIL_VARIANT_MODE: str = ""
LUCKMAIL_REUSE_PURCHASED: bool = False
LUCKMAIL_TAG_ID: Optional[int] = None
LUCKMAIL_USE_IMPORTED_POOL: bool = False
LUCKMAIL_SPECIFIED_EMAIL: str = ""

DUCKMAIL_API_URL: str = "https://api.duckmail.com"
DUCKMAIL_DOMAIN: str = ""
DUCKMAIL_MODE: str = "custom_api"
DUCK_API_TOKEN: str = ""
DUCK_COOKIE: str = ""
DUCK_OFFICIAL_API_BASE: str = "https://quack.duckduckgo.com"
DUCKMAIL_FORWARD_MODE: str = "Gmail_OAuth"
DUCKMAIL_FORWARD_EMAIL: str = ""
DUCK_USE_PROXY: bool = True

HERO_SMS_ENABLED: bool = False
HERO_SMS_API_KEY: str = ""
HERO_SMS_BASE_URL: str = "https://hero-sms.com/stubs/handler_api.php"
HERO_SMS_COUNTRY: str = "US"
HERO_SMS_SERVICE: str = "openai"
HERO_SMS_USE_PROXY: bool = False
HERO_SMS_AUTO_PICK_COUNTRY: bool = False
HERO_SMS_REUSE_PHONE: bool = True
HERO_SMS_MAX_PRICE: float = 2.0
HERO_SMS_MIN_BALANCE: float = 2.0
HERO_SMS_MAX_TRIES: int = 3
HERO_SMS_POLL_TIMEOUT_SEC: int = 120


NORMAL_SLEEP_MIN: int = 5
NORMAL_SLEEP_MAX: int = 30
NORMAL_TARGET_COUNT: int = 0

_clash_enable: bool = False
_clash_pool_mode: bool = False
WARP_PROXY_LIST: list = []
PROXY_QUEUE: queue.Queue = queue.Queue()

AI_API_BASE: str = ""
AI_API_KEY: str = ""
AI_MODEL: str = "gpt-3.5-turbo"
AI_ENABLE_PROFILE: bool = False
TG_BOT: dict = {"enable": False, "token": "", "chat_id": ""}

CLUSTER_NODE_NAME: str = ""
CLUSTER_MASTER_URL: str = ""
CLUSTER_SECRET: str = "change-me-cluster-secret"
TEMPORAM_COOKIE: str = ""
FVIA_TOKEN: str = ""
TMAILOR_CURRENT_TOKEN: str = ""
REG_MODE: str = "protocol"

def reload_all_configs():
    global _c
    global EMAIL_API_MODE, MAIL_DOMAINS, GPTMAIL_BASE, ADMIN_AUTH
    global ENABLE_SUB_DOMAINS, SUB_DOMAIN_COUNT
    global IMAP_SERVER, IMAP_PORT, IMAP_USER, IMAP_PASS
    global LOCAL_MS_ENABLE_FISSION, LOCAL_MS_POOL_FISSION, LOCAL_MS_MASTER_EMAIL, LOCAL_MS_CLIENT_ID, LOCAL_MS_REFRESH_TOKEN
    global FREEMAIL_API_URL, FREEMAIL_API_TOKEN
    global CM_API_URL, CM_ADMIN_EMAIL, CM_ADMIN_PASS
    global MC_API_BASE, MC_KEY
    global DEFAULT_PROXY, HTTP_DYNAMIC_PROXY_ENABLE, HTTP_DYNAMIC_PROXY_POOL_SIZE, HTTP_DYNAMIC_PROXY_LIST
    global SUB_DOMAIN_LEVEL,RANDOM_SUB_DOMAIN_LEVEL
    global ENABLE_MULTI_THREAD_REG, REG_THREADS, MAX_OTP_RETRIES
    global USE_PROXY_FOR_EMAIL, ENABLE_EMAIL_MASKING
    global LOGIN_DELAY_MIN, LOGIN_DELAY_MAX
    global ENABLE_CPA_MODE, SAVE_TO_LOCAL_IN_CPA_MODE
    global CPA_API_URL, CPA_API_TOKEN, MIN_ACCOUNTS_THRESHOLD, BATCH_REG_COUNT
    global MIN_REMAINING_WEEKLY_PERCENT, REMOVE_ON_LIMIT_REACHED, REMOVE_DEAD_ACCOUNTS
    global CPA_THREADS, CHECK_INTERVAL_MINUTES, ENABLE_TOKEN_REVIVE
    global NORMAL_SLEEP_MIN, NORMAL_SLEEP_MAX, NORMAL_TARGET_COUNT
    global _clash_enable, _clash_pool_mode, WARP_PROXY_LIST, PROXY_QUEUE
    global ENABLE_SUB2API_MODE, SUB2API_URL, SUB2API_KEY
    global SUB2API_MIN_THRESHOLD, SUB2API_BATCH_COUNT, SUB2API_CHECK_INTERVAL, SUB2API_THREADS
    global SUB2API_SAVE_TO_LOCAL
    global SUB2API_REMOVE_ON_LIMIT_REACHED, SUB2API_REMOVE_DEAD_ACCOUNTS, SUB2API_ENABLE_TOKEN_REVIVE
    global SUB2API_ACCOUNT_CONCURRENCY, SUB2API_ACCOUNT_LOAD_FACTOR, SUB2API_ACCOUNT_PRIORITY
    global SUB2API_ACCOUNT_RATE_MULTIPLIER, SUB2API_ACCOUNT_GROUP_IDS, SUB2API_ENABLE_WS_MODE
    global LUCKMAIL_API_KEY,LUCKMAIL_PREFERRED_DOMAIN,LUCKMAIL_EMAIL_TYPE,LUCKMAIL_VARIANT_MODE
    global LUCKMAIL_REUSE_PURCHASED, LUCKMAIL_TAG_ID, LUCKMAIL_USE_IMPORTED_POOL, LUCKMAIL_SPECIFIED_EMAIL
    global HERO_SMS_ENABLED, HERO_SMS_API_KEY, HERO_SMS_BASE_URL, HERO_SMS_COUNTRY, HERO_SMS_SERVICE, HERO_SMS_USE_PROXY
    global HERO_SMS_AUTO_PICK_COUNTRY, HERO_SMS_REUSE_PHONE, HERO_SMS_MAX_PRICE
    global HERO_SMS_MIN_BALANCE, HERO_SMS_MAX_TRIES, HERO_SMS_POLL_TIMEOUT_SEC
    global AI_API_BASE, AI_API_KEY, AI_MODEL, AI_ENABLE_PROFILE
    global CPA_AUTO_CHECK, SUB2API_AUTO_CHECK
    global TG_BOT
    global TEMPORAM_COOKIE
    global REG_MODE
    global TMAILOR_CURRENT_TOKEN
    global FVIA_TOKEN
    global DUCKMAIL_API_URL, DUCKMAIL_DOMAIN, DUCKMAIL_MODE, DUCK_API_TOKEN, DUCK_COOKIE, DUCK_OFFICIAL_API_BASE
    global DUCKMAIL_FORWARD_MODE, DUCKMAIL_FORWARD_EMAIL
    global DUCK_USE_PROXY
    global CLUSTER_NODE_NAME, CLUSTER_MASTER_URL, CLUSTER_SECRET


    def safe_int(value, default, minimum=None):
        try:
            parsed = int(str(value).strip())
        except (TypeError, ValueError):
            parsed = default
        if minimum is not None:
            return max(minimum, parsed)
        return parsed

    def safe_float(value, default, minimum=None):
        try:
            parsed = float(str(value).strip())
        except (TypeError, ValueError):
            parsed = default
        if minimum is not None:
            return max(minimum, parsed)
        return parsed

    def safe_bool(value, default=False):
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
        return default

    def parse_group_ids(raw_value):
        if isinstance(raw_value, list):
            raw_items = raw_value
        else:
            raw_items = str(raw_value or "").split(",")

        group_ids = []
        for item in raw_items:
            text = str(item).strip()
            if text.isdigit():
                group_ids.append(int(text))
        return group_ids

    def safe_int(value, default, minimum=None):
        try:
            parsed = int(str(value).strip())
        except (TypeError, ValueError):
            parsed = default
        if minimum is not None:
            return max(minimum, parsed)
        return parsed

    def safe_float(value, default, minimum=None):
        try:
            parsed = float(str(value).strip())
        except (TypeError, ValueError):
            parsed = default
        if minimum is not None:
            return max(minimum, parsed)
        return parsed

    def safe_bool(value, default=False):
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
        return default

    def parse_group_ids(raw_value):
        if isinstance(raw_value, list):
            raw_items = raw_value
        else:
            raw_items = str(raw_value or "").split(",")

        group_ids = []
        for item in raw_items:
            text = str(item).strip()
            if text.isdigit():
                group_ids.append(int(text))
        return group_ids

    _c = init_config()

    EMAIL_API_MODE   = _c.get("email_api_mode", "cloudflare_temp_email")
    MAIL_DOMAINS     = _c.get("mail_domains", "")
    GPTMAIL_BASE     = str(_c.get("gptmail_base", "")).strip().rstrip("/")
    ADMIN_AUTH       = _c.get("admin_auth", "")

    _imap            = _c.get("imap", {})
    IMAP_SERVER      = _imap.get("server", "imap.gmail.com")
    IMAP_PORT        = _imap.get("port", 993)
    IMAP_USER        = _imap.get("user", "")
    IMAP_PASS        = _imap.get("pass", "")

    _local_microsoft = _c.get("local_microsoft", {})
    LOCAL_MS_ENABLE_FISSION = bool(_local_microsoft.get("enable_fission", False))
    LOCAL_MS_POOL_FISSION = bool(_local_microsoft.get("pool_fission", False))
    LOCAL_MS_MASTER_EMAIL = str(_local_microsoft.get("master_email", "")).strip()
    LOCAL_MS_CLIENT_ID = str(_local_microsoft.get("client_id", "")).strip()
    LOCAL_MS_REFRESH_TOKEN = str(_local_microsoft.get("refresh_token", "")).strip()

    _free            = _c.get("freemail", {})
    FREEMAIL_API_URL = str(_free.get("api_url", "")).strip().rstrip("/")
    FREEMAIL_API_TOKEN = _free.get("api_token", "")
  
    _cm              = _c.get("cloudmail", {})
    CM_API_URL       = str(_cm.get("api_url", "")).strip().rstrip("/")
    CM_ADMIN_EMAIL   = _cm.get("admin_email", "")
    CM_ADMIN_PASS    = _cm.get("admin_password", "")

    _mc              = _c.get("mail_curl", {})
    MC_API_BASE      = str(_mc.get("api_base", "")).strip().rstrip("/")
    MC_KEY           = _mc.get("key", "")

    DEFAULT_PROXY    = normalize_proxy_url(_c.get("default_proxy", ""))

    ENABLE_MULTI_THREAD_REG = _c.get("enable_multi_thread_reg", False)
    REG_THREADS      = _c.get("reg_threads", 3)
    MAX_OTP_RETRIES  = _c.get("max_otp_retries", 5)
    USE_PROXY_FOR_EMAIL     = _c.get("use_proxy_for_email", False)
    ENABLE_EMAIL_MASKING    = _c.get("enable_email_masking", True)

    LOGIN_DELAY_MIN  = _c.get("login_delay_min", 20)
    LOGIN_DELAY_MAX  = _c.get("login_delay_max", 45)

    _cpa             = _c.get("cpa_mode", {})
    ENABLE_CPA_MODE  = _cpa.get("enable", False)
    SAVE_TO_LOCAL_IN_CPA_MODE = _cpa.get("save_to_local", True)
    CPA_API_URL      = format_docker_url(str(_cpa.get("api_url", "")).strip()).rstrip("/")
    CPA_API_TOKEN    = _cpa.get("api_token", "")
    MIN_ACCOUNTS_THRESHOLD  = _cpa.get("min_accounts_threshold", 30)
    BATCH_REG_COUNT  = _cpa.get("batch_reg_count", 1)
    MIN_REMAINING_WEEKLY_PERCENT = _cpa.get("min_remaining_weekly_percent", 80)
    REMOVE_ON_LIMIT_REACHED = _cpa.get("remove_on_limit_reached", False)
    REMOVE_DEAD_ACCOUNTS    = _cpa.get("remove_dead_accounts", False)
    CPA_THREADS      = _cpa.get("threads", 10)
    CHECK_INTERVAL_MINUTES  = _cpa.get("check_interval_minutes", 60)
    ENABLE_TOKEN_REVIVE     = _cpa.get("enable_token_revive", False)
    CPA_AUTO_CHECK = _cpa.get("auto_check", True)

    _sub2api = _c.get("sub2api_mode", {})
    ENABLE_SUB2API_MODE = _sub2api.get("enable", False)
    SUB2API_URL         = format_docker_url(str(_sub2api.get("api_url", "")).strip()).rstrip("/")
    SUB2API_KEY         = _sub2api.get("api_key", "")
    SUB2API_MIN_THRESHOLD = _sub2api.get("min_accounts_threshold", 70)
    SUB2API_BATCH_COUNT = _sub2api.get("batch_reg_count", 2)
    SUB2API_CHECK_INTERVAL = _sub2api.get("check_interval_minutes", 60)
    SUB2API_THREADS     = _sub2api.get("threads", 10)
    SUB2API_SAVE_TO_LOCAL = _sub2api.get("save_to_local", True)
    SUB2API_REMOVE_ON_LIMIT_REACHED = _sub2api.get("remove_on_limit_reached", True)
    SUB2API_REMOVE_DEAD_ACCOUNTS = _sub2api.get("remove_dead_accounts", True)
    SUB2API_ENABLE_TOKEN_REVIVE = _sub2api.get("enable_token_revive", False)
    SUB2API_AUTO_CHECK = _sub2api.get("auto_check", True)
    SUB2API_ACCOUNT_CONCURRENCY = safe_int(_sub2api.get("account_concurrency", 10), 10, minimum=1)
    SUB2API_ACCOUNT_LOAD_FACTOR = safe_int(_sub2api.get("account_load_factor", 10), 10, minimum=1)
    SUB2API_ACCOUNT_PRIORITY = safe_int(_sub2api.get("account_priority", 1), 1, minimum=1)
    SUB2API_ACCOUNT_RATE_MULTIPLIER = safe_float(_sub2api.get("account_rate_multiplier", 1.0), 1.0, minimum=0.0)
    SUB2API_ACCOUNT_GROUP_IDS = parse_group_ids(_sub2api.get("account_group_ids", ""))
    SUB2API_ENABLE_WS_MODE = safe_bool(_sub2api.get("enable_ws_mode", True), default=True)

    _normal          = _c.get("normal_mode", {})
    NORMAL_SLEEP_MIN = _normal.get("sleep_min", 5)
    NORMAL_SLEEP_MAX = _normal.get("sleep_max", 30)
    NORMAL_TARGET_COUNT = _normal.get("target_count", 0)

    # 自定义动态 HTTP 代理池配置。若只填一条代理，系统会按 pool_size 复制成多个工作位。
    _http_dynamic_proxy = _c.get("http_dynamic_proxy", {})
    HTTP_DYNAMIC_PROXY_ENABLE = bool(_http_dynamic_proxy.get("enable", False))
    HTTP_DYNAMIC_PROXY_POOL_SIZE = safe_int(_http_dynamic_proxy.get("pool_size", REG_THREADS), REG_THREADS, minimum=1)
    _raw_http_dynamic_list = _http_dynamic_proxy.get("proxy_list", [])
    if isinstance(_raw_http_dynamic_list, str):
        _raw_http_dynamic_list = [line.strip() for line in _raw_http_dynamic_list.splitlines() if line.strip()]
    elif not isinstance(_raw_http_dynamic_list, list):
        _raw_http_dynamic_list = []
    HTTP_DYNAMIC_PROXY_LIST = [normalize_proxy_url(p) for p in _raw_http_dynamic_list if normalize_proxy_url(p)]
    if not DEFAULT_PROXY and HTTP_DYNAMIC_PROXY_LIST:
        DEFAULT_PROXY = HTTP_DYNAMIC_PROXY_LIST[0]

    _clash_conf      = _c.get("clash_proxy_pool", {})
    _clash_enable    = _clash_conf.get("enable", False)
    _clash_pool_mode = _clash_conf.get("pool_mode", False)
    _raw_warp_proxy_list = _c.get("warp_proxy_list", [])
    if isinstance(_raw_warp_proxy_list, str):
        _raw_warp_proxy_list = [line.strip() for line in _raw_warp_proxy_list.splitlines() if line.strip()]
    elif not isinstance(_raw_warp_proxy_list, list):
        _raw_warp_proxy_list = []
    WARP_PROXY_LIST = [normalize_proxy_url(p) for p in _raw_warp_proxy_list if normalize_proxy_url(p)]
    _clash_test_proxy = normalize_proxy_url(_clash_conf.get("test_proxy_url", "http://127.0.0.1:7890"))

    # PROXY_QUEUE 是调度层统一消费的代理通道队列。
    # 优先级：
    # 1. Clash 独享池模式
    # 2. HTTP 动态代理池模式
    # 3. 单条 default_proxy / 直连
    with PROXY_QUEUE.mutex:
        PROXY_QUEUE.queue.clear()
    if _clash_enable and _clash_pool_mode:
        if WARP_PROXY_LIST:
            for p in WARP_PROXY_LIST:
                PROXY_QUEUE.put(p)
        elif _clash_test_proxy:
            print(f"[{ts()}] [WARNING] Clash 独享池已开启，但 warp_proxy_list 为空，回退使用单条 test_proxy_url 通道: {_clash_test_proxy}")
            PROXY_QUEUE.put(_clash_test_proxy)
        else:
            print(f"[{ts()}] [ERROR] Clash 独享池已开启，但未配置任何 warp_proxy_list 或 test_proxy_url，当前代理池不可用。")
    elif HTTP_DYNAMIC_PROXY_ENABLE:
        _dynamic_sources = HTTP_DYNAMIC_PROXY_LIST or ([DEFAULT_PROXY] if DEFAULT_PROXY else [])
        if _dynamic_sources:
            if len(_dynamic_sources) == 1:
                for _ in range(HTTP_DYNAMIC_PROXY_POOL_SIZE):
                    PROXY_QUEUE.put(_dynamic_sources[0])
            else:
                for idx in range(HTTP_DYNAMIC_PROXY_POOL_SIZE):
                    PROXY_QUEUE.put(_dynamic_sources[idx % len(_dynamic_sources)])
        else:
            print(f"[{ts()}] [ERROR] HTTP 动态代理池已开启，但 proxy_list 与 default_proxy 均为空，当前动态代理池不可用。")
    else:
        PROXY_QUEUE.put(DEFAULT_PROXY if DEFAULT_PROXY else None)
    _luckmail        = _c.get("luckmail", {})
    LUCKMAIL_API_KEY = _luckmail.get("api_key", "")
    LUCKMAIL_PREFERRED_DOMAIN = _luckmail.get("preferred_domain", "")
    LUCKMAIL_EMAIL_TYPE = str(_luckmail.get("email_type") or "ms_graph").strip()
    LUCKMAIL_VARIANT_MODE = str(_luckmail.get("variant_mode") or "").strip()
    LUCKMAIL_REUSE_PURCHASED = bool(_luckmail.get("reuse_purchased", False))
    LUCKMAIL_USE_IMPORTED_POOL = bool(_luckmail.get("use_imported_pool", False))
    LUCKMAIL_SPECIFIED_EMAIL = str(_luckmail.get("specified_email") or "").strip().lower()
    _raw_tag_id = _luckmail.get("tag_id")
    try:
        LUCKMAIL_TAG_ID = int(_raw_tag_id) if _raw_tag_id else None
    except (ValueError, TypeError):
        LUCKMAIL_TAG_ID = None

    SUB_DOMAIN_LEVEL = _c.get("sub_domain_level", 1)
    RANDOM_SUB_DOMAIN_LEVEL = _c.get("random_sub_domain_level", False)
    ENABLE_SUB_DOMAINS = _c.get("enable_sub_domains", False)

    _hero_sms_conf = _c.get("hero_sms", {})
    HERO_SMS_ENABLED = _hero_sms_conf.get("enabled", False)
    HERO_SMS_API_KEY = _hero_sms_conf.get("api_key", "")
    HERO_SMS_BASE_URL = str(_hero_sms_conf.get("base_url", "https://hero-sms.com/stubs/handler_api.php")).strip().rstrip("/")
    HERO_SMS_COUNTRY = _hero_sms_conf.get("country", "US")
    HERO_SMS_SERVICE = _hero_sms_conf.get("service", "dr")
    HERO_SMS_USE_PROXY = safe_bool(_hero_sms_conf.get("use_proxy", False), default=False)
    HERO_SMS_AUTO_PICK_COUNTRY = _hero_sms_conf.get("auto_pick_country", False)
    HERO_SMS_REUSE_PHONE = _hero_sms_conf.get("reuse_phone", True)

    try:
        HERO_SMS_MAX_PRICE = float(_hero_sms_conf.get("max_price", 2.0))
    except:
        HERO_SMS_MAX_PRICE = 2.0

    try:
        HERO_SMS_MIN_BALANCE = float(_hero_sms_conf.get("min_balance", 2.0))
    except:
        HERO_SMS_MIN_BALANCE = 2.0

    try:
        HERO_SMS_MAX_TRIES = int(_hero_sms_conf.get("max_tries", 3))
    except:
        HERO_SMS_MAX_TRIES = 3

    try:
        HERO_SMS_POLL_TIMEOUT_SEC = int(_hero_sms_conf.get("poll_timeout_sec", 120))
    except:
        HERO_SMS_POLL_TIMEOUT_SEC = 120


    _ai = _c.get("ai_service", {})
    AI_API_BASE = str(_ai.get("api_base", "https://api.openai.com/v1")).strip().rstrip("/")
    AI_API_KEY = _ai.get("api_key", "")
    AI_MODEL = _ai.get("model", "gpt-3.5-turbo")
    AI_ENABLE_PROFILE = _ai.get("enable_profile", False)

    _tg = _c.get("tg_bot", {})
    TG_BOT = {
        "enable": _tg.get("enable", False),
        "token": str(_tg.get("token", "")),
        "chat_id": str(_tg.get("chat_id", "")),
        "use_proxy": _tg.get("use_proxy", False),
        "mask_email": _tg.get("mask_email", False),
        "mask_password": _tg.get("mask_password", False),
        "template_success": _tg.get("template_success",
                                    "🎉 <b>注册成功</b>\n━━━━━━━━━━━━\n⏰ 时间：<code>{time}</code>\n📧 账号：<code>{email}</code>\n🔑 密码：<code>{password}</code>"),
        "template_stop": _tg.get("template_stop",
                                 "🛑 <b>任务已停止</b>\n━━━━━━━━━━━━\n📊 成功率：<code>{success_rate}%</code>\n✅ 成功：<code>{success}/{target}</code>\n❌ 失败：<code>{failed}</code>\n🚧 风控：<code>{retries}</code>\n🔒 密码受阻：<code>{pwd_blocked}</code>\n📱 出现手机：<code>{phone_verify}</code>\n⏱ 总耗时：<code>{elapsed_time}s</code>\n📈 平均单号：<code>{avg_time}s</code>")
    }

    _duck = _c.get("duckmail", {})
    DUCKMAIL_API_URL = str(_duck.get("api_url") or "https://api.duckmail.com").rstrip("/")
    DUCKMAIL_DOMAIN = str(_duck.get("domain") or "").strip()
    DUCKMAIL_MODE = str(_duck.get("mode") or "custom_api").strip().lower()
    DUCK_API_TOKEN = str(_duck.get("duck_api_token") or "").strip()
    DUCK_COOKIE = str(_duck.get("duck_cookie") or "").strip()
    DUCK_OFFICIAL_API_BASE = str(_duck.get("duck_api_base_url") or "https://quack.duckduckgo.com").rstrip("/")
    DUCKMAIL_FORWARD_MODE = str(_duck.get("forward_mode") or "Gmail_OAuth").strip()
    DUCKMAIL_FORWARD_EMAIL = str(_duck.get("forward_email") or "").strip()
    DUCK_USE_PROXY = safe_bool(_duck.get("use_proxy", True), default=True)

    CLUSTER_NODE_NAME = str(_c.get("cluster_node_name", "")).strip()
    CLUSTER_MASTER_URL = str(_c.get("cluster_master_url", "")).strip().rstrip("/")
    CLUSTER_SECRET = str(_c.get("cluster_secret", "change-me-cluster-secret")).strip()
    REG_MODE = str(_c.get("reg_mode", "protocol")).strip().lower()

    _temporam = _c.get("temporam", {})
    TEMPORAM_COOKIE = str(_temporam.get("cookie") or "").strip()

    _tmailor = _c.get("tmailor", {})
    TMAILOR_CURRENT_TOKEN = str(_tmailor.get("current_token") or "").strip()

    _fvia = _c.get("fvia", {})
    FVIA_TOKEN = str(_fvia.get("token") or "").strip()
    reload_proxy_config()
    print(f"[{ts()}] [系统] 核心配置已完成同步。")

reload_all_configs()

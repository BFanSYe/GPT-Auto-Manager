import os
import time
import json
import secrets
import re
import random
import asyncio
import traceback
import threading
import sys
import subprocess
import shlex
import urllib.parse
import yaml
import httpx
from fastapi import APIRouter, Depends, Header, Query, Request, WebSocket, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional

from cloudflare import Cloudflare
from utils import core_engine, db_manager
from utils.config import reload_all_configs
from utils.integrations.sub2api_client import Sub2APIClient
from utils.integrations.tg_notifier import send_tg_msg_async
from utils.email_providers.gmail_oauth_handler import GmailOAuthHandler

from global_state import VALID_TOKENS, CLUSTER_NODES, NODE_COMMANDS, cluster_lock, log_history, engine, verify_token, worker_status
import utils.config as cfg

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "data", "config.yaml")
GMAIL_CLIENT_SECRETS = os.path.join(BASE_DIR, "data", "credentials.json")
GMAIL_TOKEN_PATH = os.path.join(BASE_DIR, "data", "token.json")
GMAIL_VERIFIER_PATH = os.path.join(BASE_DIR, "data", "temp_verifier.txt")
CLASH_POOL_ROOT = "/opt/mihomo-pool"
CLASH_POOL_ENV_PATH = os.path.join(CLASH_POOL_ROOT, "pool.env")
CLASH_POOL_UPDATE_SCRIPT = os.path.join(CLASH_POOL_ROOT, "update_pool.sh")
CLASH_POOL_STATUS_SCRIPT = os.path.join(CLASH_POOL_ROOT, "status_pool.sh")

class DummyArgs:
    def __init__(self, proxy=None, once=False):
        self.proxy = proxy
        self.once = once


class ExportReq(BaseModel): emails: list[str]


class DeleteReq(BaseModel): emails: list[str]


class LoginData(BaseModel): password: str


class CFSyncExistingReq(BaseModel): sub_domains: str; api_email: str; api_key: str


class LuckMailBulkBuyReq(BaseModel): quantity: int; auto_tag: bool; config: dict


class SMSPriceReq(BaseModel): service: str = "openai"


class GmailExchangeReq(BaseModel): code: str


class CloudAccountItem(BaseModel): id: str; type: str


class CloudActionReq(BaseModel): accounts: List[CloudAccountItem]; action: str


class ClusterUploadAccountsReq(BaseModel): node_name: str; secret: str; accounts: list


class ClusterReportReq(BaseModel): node_name: str; secret: str; stats: dict; logs: list


class ClusterControlReq(BaseModel): node_name: str; action: str


class ClashPoolUpdateReq(BaseModel): sub_url: str


class ExtResultReq(BaseModel):
    status: str
    task_id: Optional[str] = ""
    email: Optional[str] = ""
    password: Optional[str] = ""
    error_msg: Optional[str] = ""
    token_data: Optional[str] = ""
    callback_url: Optional[str] = ""
    code_verifier: Optional[str] = ""
    expected_state: Optional[str] = ""
    error_type: Optional[str] = "failed"


# ==========================================
# 辅助函数
# ==========================================
def get_web_password():
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                c = yaml.safe_load(f) or {}
                return str(c.get("web_password", "admin")).strip()
    except Exception:
        pass
    return "admin"


def _normalize_proxy_input_for_save(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if "://" not in text:
        text = f"http://{text}"
    return text


def _normalize_proxy_input_list_for_save(raw_value) -> list[str]:
    if isinstance(raw_value, str):
        raw_items = [line.strip() for line in raw_value.splitlines() if line.strip()]
    elif isinstance(raw_value, list):
        raw_items = raw_value
    else:
        raw_items = []
    cleaned = []
    for item in raw_items:
        normalized = _normalize_proxy_input_for_save(item)
        if normalized:
            cleaned.append(normalized)
    return cleaned


def _build_http_dynamic_proxy_runtime() -> dict:
    enabled = bool(getattr(cfg, "HTTP_DYNAMIC_PROXY_ENABLE", False))
    configured_pool_size = int(getattr(cfg, "HTTP_DYNAMIC_PROXY_POOL_SIZE", 0) or 0)
    source_list = getattr(cfg, "HTTP_DYNAMIC_PROXY_LIST", []) or []
    default_proxy = str(getattr(cfg, "DEFAULT_PROXY", "") or "").strip()
    clash_pool_active = bool(getattr(cfg, "_clash_enable", False) and getattr(cfg, "_clash_pool_mode", False))

    queue_items = []
    try:
        with cfg.PROXY_QUEUE.mutex:
            queue_items = list(cfg.PROXY_QUEUE.queue)
    except Exception:
        queue_items = []

    actual_queue_channels = len([item for item in queue_items if item])
    using_default_fallback = enabled and not source_list and bool(default_proxy)
    invalid_empty = enabled and not source_list and not default_proxy
    single_source = (len(source_list) == 1) or using_default_fallback
    queue_owner = "clash" if clash_pool_active else ("http_dynamic" if enabled else "default")
    loaded_channels = actual_queue_channels if enabled and queue_owner == "http_dynamic" else 0
    single_source_cloned = enabled and single_source and loaded_channels > 1

    mode = "disabled"
    message = "HTTP 动态代理池未启用"
    if enabled:
        if queue_owner == "clash":
            mode = "shadowed_by_clash"
            message = "HTTP 动态代理池已开启，但当前 Clash 独享池优先级更高，动态代理池未进入运行队列"
        elif invalid_empty:
            mode = "invalid_empty"
            message = "已开启，但未填写 proxy_list 且未配置 default_proxy，运行时不会装载任何动态通道"
        elif using_default_fallback:
            mode = "fallback_default_proxy"
            message = "未填写动态代理列表，当前回退使用 default_proxy 构建动态通道队列"
        elif len(source_list) == 1:
            mode = "single_source_cloned"
            message = "单条动态代理已按通道数复制为多个并发工作位，适合按连接/会话轮换出口的网关"
        elif len(source_list) > 1:
            mode = "multi_source_round_robin"
            message = "多条动态代理已按通道数轮询装载到运行队列"
        else:
            mode = "unknown"
            message = "当前运行态已启用，但未识别到明确的动态代理来源"

    return {
        "enabled": enabled,
        "queue_owner": queue_owner,
        "configured_pool_size": configured_pool_size,
        "source_count": len(source_list),
        "loaded_channels": loaded_channels,
        "using_default_fallback": using_default_fallback,
        "single_source_cloned": single_source_cloned,
        "mode": mode,
        "queue_ready": bool(enabled and queue_owner == "http_dynamic" and loaded_channels > 0 and not invalid_empty),
        "error": "HTTP 动态代理池已开启，但当前没有任何可装载的动态代理通道" if invalid_empty else "",
        "message": message,
    }


def _read_clash_pool_env() -> dict:
    """读取宿主机 Mihomo 代理池的环境文件。"""
    if not os.path.exists(CLASH_POOL_ENV_PATH):
        raise FileNotFoundError(f"未找到 {CLASH_POOL_ENV_PATH}")
    env_map = {}
    with open(CLASH_POOL_ENV_PATH, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            env_map[key] = value
    return env_map


def _write_clash_pool_env(env_map: dict) -> None:
    """回写代理池配置，只覆盖关键环境项并保留其余扩展字段。"""
    primary_keys = ["COUNT", "SUB_URL", "SECRET", "IMAGE"]
    lines = []
    for key in primary_keys:
        if key in env_map:
            lines.append(f"{key}={shlex.quote(str(env_map[key]))}")
    for key, value in env_map.items():
        if key not in primary_keys:
            lines.append(f"{key}={shlex.quote(str(value))}")
    with open(CLASH_POOL_ENV_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")


def _run_clash_pool_script(script_path: str, timeout: int = 300) -> tuple[int, str]:
    """在容器内执行宿主机代理池脚本，并返回退出码与输出。"""
    proc = subprocess.run(
        ["bash", script_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout,
        cwd=CLASH_POOL_ROOT if os.path.isdir(CLASH_POOL_ROOT) else None,
    )
    return proc.returncode, proc.stdout or ""


def _get_clash_pool_status_output() -> str:
    if not os.path.exists(CLASH_POOL_STATUS_SCRIPT):
        return ""
    try:
        _, output = _run_clash_pool_script(CLASH_POOL_STATUS_SCRIPT, timeout=20)
        return output.strip()
    except Exception as e:
        return f"状态读取失败: {e}"


def _get_clash_pool_group_candidates(env_map: dict | None = None) -> tuple[list[dict], str]:
    """通过 Mihomo controller API 读取当前真实策略组。

    这样前端在订阅更新后可以直接展示“现在到底有哪些策略组可选”，
    避免用户手动猜 group_name。
    """
    try:
        env_map = env_map or _read_clash_pool_env()
        secret = str(env_map.get("SECRET") or "").strip()
        count = int(env_map.get("COUNT") or 1)
        api_port = 42001 if count > 0 else 42001
        url = f"http://host.docker.internal:{api_port}/proxies"
        headers = {"Authorization": f"Bearer {secret}"} if secret else {}
        resp = httpx.get(url, headers=headers, timeout=15.0)
        if resp.status_code != 200:
            return [], f"读取 Clash API 失败: HTTP {resp.status_code}"
        data = resp.json()
        proxies = data.get("proxies") or {}
        groups = []
        for name, meta in proxies.items():
            if not isinstance(meta, dict):
                continue
            all_items = meta.get("all")
            now_name = meta.get("now")
            if not isinstance(all_items, list):
                continue
            groups.append({
                "name": str(name),
                "current": str(now_name or ""),
                "node_count": len(all_items),
            })
        groups.sort(key=lambda x: (-int(x.get("node_count") or 0), x.get("name") or ""))
        return groups, ""
    except Exception as e:
        return [], f"读取策略组失败: {e}"


def _sanitize_clash_sub_url(sub_url: str) -> str:
    value = str(sub_url or "").strip().strip("'\"")
    return re.sub(r"\s+", "", value)


def _replace_query_param(url: str, key: str, value: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    items = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    out = []
    replaced = False
    for k, v in items:
        if k == key:
            if not replaced:
                out.append((k, value))
                replaced = True
            continue
        out.append((k, v))
    if not replaced:
        out.append((key, value))
    return urllib.parse.urlunsplit(parsed._replace(query=urllib.parse.urlencode(out, doseq=True)))


def _build_clash_sub_url_candidates(sub_url: str) -> list[str]:
    normalized = _sanitize_clash_sub_url(sub_url)
    if not normalized:
        return []
    candidates = [normalized]
    parsed = urllib.parse.urlsplit(normalized)
    query_map = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    current_flag = str(query_map.get("flag") or "").strip().lower()

    if current_flag != "mihomo":
        candidates.append(_replace_query_param(normalized, "flag", "mihomo"))
    if not current_flag:
        candidates.append(_replace_query_param(normalized, "flag", "clash-meta"))
        candidates.append(_replace_query_param(normalized, "flag", "clash"))

    seen = set()
    ordered = []
    for item in candidates:
        if item and item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _classify_sub_payload(text: str) -> str:
    body = str(text or "").strip()
    if not body:
        return "empty"
    lowered = body[:256].lower()
    if lowered.startswith("<!doctype html") or lowered.startswith("<html"):
        return "html"
    if any(token in body for token in ["proxy-groups:", "proxy-providers:", "\nproxies:", "\nrules:", "mixed-port:"]):
        return "yaml"
    compact = re.sub(r"\s+", "", body)
    if "://" in body and any(proto in body for proto in ["ss://", "vmess://", "vless://", "trojan://", "hysteria://", "hy2://", "tuic://"]):
        return "raw-uri"
    if len(compact) > 128 and re.fullmatch(r"[A-Za-z0-9+/=_-]+", compact or ""):
        return "base64"
    return "unknown"


def _probe_clash_sub_url(sub_url: str) -> dict:
    result = {
        "url": sub_url,
        "ok": False,
        "reason": "",
        "http_status": None,
        "payload_kind": "",
        "proxy_count": 0,
        "provider_count": 0,
        "group_count": 0,
        "group_names": [],
        "tls_insecure_fallback": False,
    }
    last_error = ""

    for verify_tls in (True, False):
        if verify_tls is False and result["http_status"] is not None:
            break
        try:
            resp = httpx.get(
                sub_url,
                timeout=25.0,
                follow_redirects=True,
                verify=verify_tls,
                headers={"User-Agent": "openai-cpa/subscription-probe"},
            )
            result["http_status"] = resp.status_code
            if verify_tls is False:
                result["tls_insecure_fallback"] = True
            if resp.status_code != 200:
                result["reason"] = f"HTTP {resp.status_code}"
                return result

            text = resp.text or ""
            result["payload_kind"] = _classify_sub_payload(text)
            if result["payload_kind"] in {"base64", "raw-uri"}:
                result["reason"] = "返回的是通用订阅串，不是 Mihomo/Clash YAML"
                return result
            if result["payload_kind"] == "html":
                result["reason"] = "返回的是 HTML 页面，不是订阅配置"
                return result
            if result["payload_kind"] == "empty":
                result["reason"] = "订阅内容为空"
                return result

            try:
                data = yaml.safe_load(text)
            except Exception as e:
                result["reason"] = f"YAML 解析失败: {e}"
                return result

            if not isinstance(data, dict):
                result["reason"] = "订阅返回内容不是 YAML 字典结构"
                return result

            proxies = data.get("proxies") or []
            proxy_providers = data.get("proxy-providers") or {}
            groups = data.get("proxy-groups") or []

            if isinstance(proxies, list):
                result["proxy_count"] = len(proxies)
            elif isinstance(proxies, dict):
                result["proxy_count"] = len(proxies)

            if isinstance(proxy_providers, dict):
                result["provider_count"] = len(proxy_providers)

            if isinstance(groups, list):
                result["group_count"] = len(groups)
                result["group_names"] = [
                    str(item.get("name") or "").strip()
                    for item in groups
                    if isinstance(item, dict) and str(item.get("name") or "").strip()
                ]

            if result["group_count"] <= 0:
                result["reason"] = "订阅未包含任何策略组"
                return result
            if result["proxy_count"] <= 0 and result["provider_count"] <= 0:
                result["reason"] = "订阅中未包含任何节点或代理提供器"
                return result

            result["ok"] = True
            if result["tls_insecure_fallback"]:
                result["reason"] = "已使用 TLS 非校验回退探测成功"
            return result
        except Exception as e:
            last_error = str(e)
            if verify_tls is False:
                break
            continue

    result["reason"] = last_error or "订阅探测失败"
    return result


def _resolve_clash_sub_url(sub_url: str) -> tuple[dict | None, list[dict]]:
    probes = []
    for candidate in _build_clash_sub_url_candidates(sub_url):
        probe = _probe_clash_sub_url(candidate)
        probes.append(probe)
        if probe.get("ok"):
            return probe, probes
    return None, probes


def _get_clash_pool_api_urls(env_map: dict | None = None) -> list[str]:
    env_map = env_map or _read_clash_pool_env()
    try:
        count = max(1, int(env_map.get("COUNT") or 1))
    except Exception:
        count = 1
    return [f"http://host.docker.internal:{42000 + i}" for i in range(1, count + 1)]


def _get_clash_pool_config_path(env_map: dict | None = None) -> str:
    env_map = env_map or _read_clash_pool_env()
    try:
        count = max(1, int(env_map.get("COUNT") or 1))
    except Exception:
        count = 1
    for idx in range(1, count + 1):
        path = os.path.join(CLASH_POOL_ROOT, f"config_{idx}", "config.yaml")
        if os.path.exists(path):
            return path
    return os.path.join(CLASH_POOL_ROOT, "config_1", "config.yaml")


def _extract_default_route_groups(env_map: dict | None = None) -> list[str]:
    try:
        config_path = _get_clash_pool_config_path(env_map)
        if not os.path.exists(config_path):
            return []
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        rules = data.get("rules") or []
        for raw in reversed(rules):
            if not isinstance(raw, str):
                continue
            parts = [str(x).strip().strip("'\"") for x in raw.split(",")]
            if len(parts) >= 2 and parts[0].upper() in {"MATCH", "FINAL"}:
                return [parts[1]]
    except Exception:
        pass
    return []


def _find_actual_group_name(proxies: dict, keyword: str) -> str:
    wanted = str(keyword or "").strip()
    wanted_lower = wanted.lower()
    ai_hints = ["chatgpt", "openai", "copilot", "claude", "anthropic", "ai"]
    fallback_name = ""
    fallback_score = None
    for key, meta in proxies.items():
        if not isinstance(meta, dict):
            continue
        all_items = meta.get("all")
        if not isinstance(all_items, list):
            continue
        name = str(key or "").strip()
        if not name:
            continue
        leaf_count = 0
        child_group_count = 0
        for item in all_items:
            child = str(item or "").strip()
            if not child:
                continue
            child_meta = proxies.get(child)
            if isinstance(child_meta, dict) and isinstance(child_meta.get("all"), list):
                child_group_count += 1
            else:
                leaf_count += 1

        score = [0, 0, leaf_count, -child_group_count, len(all_items), -len(name)]
        if wanted and name == wanted:
            score[0] = 100
        elif wanted and wanted_lower == name.lower():
            score[0] = 95
        elif wanted and wanted_lower in name.lower():
            score[0] = 90
        elif any(hint in name.lower() for hint in ai_hints):
            score[0] = 70
        elif child_group_count == 0:
            score[0] = 50

        if wanted and any(wanted_lower in str(item or "").strip().lower() for item in all_items):
            score[1] += 5
        if any(hint in name.lower() for hint in ai_hints):
            score[1] += 3

        score_tuple = tuple(score)
        if fallback_score is None or score_tuple > fallback_score:
            fallback_score = score_tuple
            fallback_name = name
    return fallback_name


def _find_group_path(proxies: dict, start_group: str, target_group: str) -> list[str]:
    start = str(start_group or "").strip()
    target = str(target_group or "").strip()
    if not start or not target:
        return []
    if start == target:
        return [start]

    queue_items: list[tuple[str, list[str]]] = [(start, [start])]
    visited = {start}

    while queue_items:
        current, path = queue_items.pop(0)
        meta = proxies.get(current)
        if not isinstance(meta, dict):
            continue
        all_items = meta.get("all")
        if not isinstance(all_items, list):
            continue
        for raw in all_items:
            child = str(raw or "").strip()
            if not child:
                continue
            if child == target:
                return path + [target]
            child_meta = proxies.get(child)
            if isinstance(child_meta, dict) and isinstance(child_meta.get("all"), list) and child not in visited:
                visited.add(child)
                queue_items.append((child, path + [child]))
    return []


def _filter_assignable_nodes(proxies: dict, group_name: str, blacklist: list[str]) -> list[str]:
    group_meta = proxies.get(group_name) if isinstance(proxies, dict) else None
    all_nodes = group_meta.get("all", []) if isinstance(group_meta, dict) else []
    valid_nodes = []
    for raw in all_nodes:
        node_name = str(raw or "").strip()
        if not node_name or node_name == group_name:
            continue
        node_meta = proxies.get(node_name, {})
        if isinstance(node_meta, dict) and isinstance(node_meta.get("all"), list):
            continue
        upper_name = node_name.upper()
        if any(str(flag or "").strip().upper() in upper_name for flag in blacklist):
            continue
        valid_nodes.append(node_name)
    return valid_nodes


def _align_default_route_group(api_url: str, headers: dict, proxies_payload: dict, default_group: str, target_group: str) -> tuple[list[dict], str]:
    path = _find_group_path(proxies_payload, default_group, target_group)
    if not path:
        return [], f"默认路由组 {default_group} 无法到达 {target_group}"
    if len(path) < 2:
        return [], ""

    ops = []
    for idx in range(len(path) - 1):
        parent = path[idx]
        child = path[idx + 1]
        try:
            resp = httpx.put(
                f"{api_url}/proxies/{urllib.parse.quote(parent, safe='')}",
                headers=headers,
                json={"name": child},
                timeout=8.0,
            )
            if resp.status_code == 204:
                ops.append({"group": parent, "select": child, "ok": True})
            else:
                ops.append({"group": parent, "select": child, "ok": False, "status": resp.status_code})
        except Exception as e:
            ops.append({"group": parent, "select": child, "ok": False, "error": str(e)})
    failed = [x for x in ops if not x.get("ok")]
    if failed:
        return ops, f"默认路由组对齐失败 {len(failed)} 项"
    return ops, ""


def _sync_clash_group_name(actual_group_name: str) -> dict:
    actual = str(actual_group_name or "").strip()
    if not actual:
        return {"updated": False, "before": "", "after": ""}

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            conf = yaml.safe_load(f) or {}
        clash_conf = conf.setdefault("clash_proxy_pool", {})
        before = str(clash_conf.get("group_name") or "").strip()
        if before == actual:
            return {"updated": False, "before": before, "after": actual}
        clash_conf["group_name"] = actual
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.dump(conf, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
        try:
            reload_all_configs()
        except Exception:
            pass
        return {"updated": True, "before": before, "after": actual}
    except Exception as e:
        return {"updated": False, "before": "", "after": actual, "error": str(e)}


def _rollback_clash_pool_update(previous_env: dict) -> tuple[int, str]:
    _write_clash_pool_env(previous_env)
    return _run_clash_pool_script(CLASH_POOL_UPDATE_SCRIPT, timeout=420)


def _spread_clash_pool_nodes(env_map: dict | None = None) -> tuple[list[dict], str]:
    """订阅更新后，为每个 Mihomo 实例尽量分配不同节点，避免全都落在同一出口。"""
    try:
        env_map = env_map or _read_clash_pool_env()
        secret = str(env_map.get("SECRET") or "").strip()
        headers = {"Authorization": f"Bearer {secret}"} if secret else {}
        api_urls = _get_clash_pool_api_urls(env_map)
        group_keyword = str(getattr(cfg, "_c", {}).get("clash_proxy_pool", {}).get("group_name", "") or "").strip()
        blacklist = getattr(cfg, "_c", {}).get("clash_proxy_pool", {}).get("blacklist", []) or []
        default_route_groups = _extract_default_route_groups(env_map)
        if not isinstance(blacklist, list):
            blacklist = []

        proxies_payload = None
        group_name = ""
        last_err = ""

        for _ in range(20):
            try:
                resp = httpx.get(f"{api_urls[0]}/proxies", headers=headers, timeout=8.0)
                if resp.status_code == 200:
                    proxies_payload = resp.json().get("proxies") or {}
                    group_name = _find_actual_group_name(proxies_payload, group_keyword)
                    if group_name:
                        break
                    last_err = f"未找到策略组关键词: {group_keyword or '（空）'}"
                else:
                    last_err = f"HTTP {resp.status_code}"
            except Exception as e:
                last_err = str(e)
            time.sleep(1.0)

        if not isinstance(proxies_payload, dict) or not group_name:
            return [], f"策略组分流失败: {last_err or '未读取到代理信息'}"

        valid_nodes = _filter_assignable_nodes(proxies_payload, group_name, blacklist)
        if not valid_nodes:
            return [], f"策略组 {group_name} 下无可分配节点（可能被黑名单过滤空）"

        random.shuffle(valid_nodes)
        assigned = []
        encoded_group = urllib.parse.quote(group_name, safe="")
        for idx, api_url in enumerate(api_urls):
            node_name = valid_nodes[idx % len(valid_nodes)]
            try:
                switch_resp = httpx.put(
                    f"{api_url}/proxies/{encoded_group}",
                    headers=headers,
                    json={"name": node_name},
                    timeout=8.0,
                )
                if switch_resp.status_code == 204:
                    align_ops = []
                    align_error = ""
                    for root_group in default_route_groups:
                        ops, err = _align_default_route_group(api_url, headers, proxies_payload, root_group, group_name)
                        if ops:
                            align_ops.extend(ops)
                        if err and not align_error:
                            align_error = err
                    assigned.append({
                        "api": api_url,
                        "group": group_name,
                        "node": node_name,
                        "ok": True if not align_error else False,
                        "route_align": align_ops,
                        "route_group": default_route_groups,
                        "route_error": align_error
                    })
                else:
                    assigned.append({"api": api_url, "group": group_name, "node": node_name, "ok": False, "status": switch_resp.status_code})
            except Exception as e:
                assigned.append({"api": api_url, "group": group_name, "node": node_name, "ok": False, "error": str(e)})

        failed = [x for x in assigned if not x.get("ok")]
        if failed:
            return assigned, f"策略组分流部分失败，共 {len(failed)} 个实例未成功切换"
        return assigned, ""
    except Exception as e:
        return [], f"策略组分流异常: {e}"


def _inspect_clash_pool_runtime(env_map: dict | None = None) -> tuple[dict, str]:
    try:
        env_map = env_map or _read_clash_pool_env()
        secret = str(env_map.get("SECRET") or "").strip()
        headers = {"Authorization": f"Bearer {secret}"} if secret else {}
        api_urls = _get_clash_pool_api_urls(env_map)
        default_route_groups = _extract_default_route_groups(env_map)
        group_keyword = str(getattr(cfg, "_c", {}).get("clash_proxy_pool", {}).get("group_name", "") or "").strip()

        runtime = {
            "group_keyword": group_keyword,
            "actual_group_name": "",
            "default_route_groups": default_route_groups,
            "effective_sub_url": str(env_map.get("SUB_URL") or "").strip(),
            "instance_total": len(api_urls),
            "instance_ok_count": 0,
            "aligned_count": 0,
            "all_aligned": None,
            "instances": [],
        }
        errors = []

        for idx, api_url in enumerate(api_urls, start=1):
            item = {
                "slot": idx,
                "api": api_url,
                "ok": False,
                "group": "",
                "current_node": "",
                "route_aligned": None,
                "route_states": [],
                "error": "",
            }
            try:
                resp = httpx.get(f"{api_url}/proxies", headers=headers, timeout=8.0)
                if resp.status_code != 200:
                    item["error"] = f"HTTP {resp.status_code}"
                    errors.append(f"{idx}号机 {item['error']}")
                    runtime["instances"].append(item)
                    continue

                proxies_payload = resp.json().get("proxies") or {}
                actual_group_name = _find_actual_group_name(proxies_payload, group_keyword)
                current_node = str((proxies_payload.get(actual_group_name) or {}).get("now") or "").strip() if actual_group_name else ""
                route_aligned = True if default_route_groups and actual_group_name else None
                route_states = []

                for root_group in default_route_groups:
                    root_meta = proxies_payload.get(root_group) or {}
                    root_now = str(root_meta.get("now") or "").strip()
                    path = _find_group_path(proxies_payload, root_group, actual_group_name) if actual_group_name else []
                    aligned = bool(path) and all(
                        str((proxies_payload.get(path[path_idx]) or {}).get("now") or "").strip() == path[path_idx + 1]
                        for path_idx in range(len(path) - 1)
                    )
                    if route_aligned is not None:
                        route_aligned = route_aligned and aligned
                    route_states.append({
                        "group": root_group,
                        "now": root_now,
                        "path": path,
                        "aligned": aligned,
                    })

                item.update({
                    "ok": True,
                    "group": actual_group_name,
                    "current_node": current_node,
                    "route_aligned": route_aligned,
                    "route_states": route_states,
                })
                if actual_group_name and not runtime["actual_group_name"]:
                    runtime["actual_group_name"] = actual_group_name
                runtime["instance_ok_count"] += 1
                if route_aligned is True:
                    runtime["aligned_count"] += 1
            except Exception as e:
                item["error"] = str(e)
                errors.append(f"{idx}号机 {e}")
            runtime["instances"].append(item)

        if default_route_groups:
            runtime["all_aligned"] = runtime["aligned_count"] == runtime["instance_ok_count"] and runtime["instance_ok_count"] > 0

        return runtime, "；".join(errors[:5])
    except Exception as e:
        return {}, f"读取 Clash 运行态失败: {e}"

def parse_cpa_usage_to_details(raw_usage: dict) -> dict:
    details = {"is_cpa": True}
    try:
        payload = raw_usage
        if "body" in raw_usage and isinstance(raw_usage["body"], str):
            try:
                payload = json.loads(raw_usage["body"])
            except:
                pass
        details["cpa_plan_type"] = str(payload.get("plan_type", "未知")).upper()
        total = payload.get("total_granted") or payload.get("hard_limit_usd") or payload.get("total")
        used = payload.get("total_used") or payload.get("total_usage") or payload.get("used")
        if total is not None and used is not None:
            total_val = float(total)
            used_val = float(used)
            details["cpa_total"] = f"${total_val:.2f}"
            details["cpa_remaining"] = f"${max(0.0, total_val - used_val):.2f}"
        else:
            details["cpa_total"] = "100%"
            details["cpa_remaining"] = "未知"

        rate_limit = payload.get("rate_limit", {})
        if isinstance(rate_limit, dict):
            primary = rate_limit.get("primary_window", {})
            if primary:
                p_remain = primary.get("remaining_percent")
                if p_remain is None and primary.get("used_percent") is not None:
                    p_remain = 100.0 - float(primary.get("used_percent"))
                details["cpa_primary_remain_pct"] = round(float(p_remain if p_remain is not None else 100.0), 1)

        code_review = payload.get("code_review_rate_limit", {})
        if isinstance(code_review, dict):
            c_primary = code_review.get("primary_window", {})
            if c_primary:
                c_remain = c_primary.get("remaining_percent")
                if c_remain is None and c_primary.get("used_percent") is not None:
                    c_remain = 100.0 - float(c_primary.get("used_percent"))
                details["cpa_codex_remain_pct"] = round(float(c_remain if c_remain is not None else 100.0), 1)

        details["cpa_used_percent"] = round(100.0 - details.get("cpa_primary_remain_pct", 100.0), 1)
        return details
    except Exception as e:
        print(f"[DEBUG] 解析CPA用量异常: {e}")
    details["cpa_total"] = "0.00";
    details["cpa_remaining"] = "0.00";
    details["cpa_used_percent"] = 0.0;
    details["cpa_plan_type"] = "未知"
    return details

@router.get("/")
async def get_dashboard():
    version = "1.0.0"
    js_path = os.path.join(BASE_DIR, "static", "js", "app.js")
    try:
        if os.path.exists(js_path):
            with open(js_path, "r", encoding="utf-8") as f:
                match = re.search(r"appVersion:\s*['\"]([^'\"]+)['\"]", f.read())
                if match: version = match.group(1)
    except Exception:
        pass

    html_path = os.path.join(BASE_DIR, "index.html")
    if not os.path.exists(html_path): return HTMLResponse(content="<h1>找不到 index.html</h1>", status_code=404)

    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content.replace("__VER__", version),
                        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"})


@router.post("/api/login")
async def login(data: LoginData):
    if data.password == get_web_password():
        token = secrets.token_hex(16)
        VALID_TOKENS.add(token)
        return {"status": "success", "token": token}
    return {"status": "error", "message": "密码错误"}


@router.get("/api/status")
async def get_status(token: str = Depends(verify_token)):
    ext_running = bool(getattr(core_engine.cfg, "REG_MODE", "protocol") == "extension" and core_engine.run_stats.get("ext_is_running"))
    return {"is_running": engine.is_running() or ext_running}

@router.post("/api/start")
async def start_task(token: str = Depends(verify_token)):
    if engine.is_running(): return {"status": "error", "message": "任务已经在运行中！"}
    try:
        reload_all_configs()
    except Exception as e:
        print(f"[{core_engine.ts()}] [警告] 启动重载提示: {e}")

    if getattr(core_engine.cfg, 'REG_MODE', 'protocol') == 'extension':
        return {"status": "error", "message": "当前为古法插件模式，请使用前端【古法】模式和浏览器插件启动。"}

    default_proxy = getattr(core_engine.cfg, 'DEFAULT_PROXY', None)
    args = DummyArgs(proxy=default_proxy if default_proxy else None)
    core_engine.run_stats.update({"success": 0, "failed": 0, "retries": 0, "pwd_blocked": 0, "phone_verify": 0, "start_time": time.time(), "ext_is_running": False})
    if getattr(core_engine.cfg, 'ENABLE_CPA_MODE', False):
        core_engine.run_stats["target"] = 0
        engine.start_cpa(args)
        return {"status": "success", "message": "启动成功：已自动识别并开启 [CPA 智能仓管模式]"}
    elif getattr(core_engine.cfg, 'ENABLE_SUB2API_MODE', False):
        engine.start_sub2api(args)
        return {"status": "success", "message": "启动成功：已自动识别并开启 [Sub2API 仓管模式]"}
    else:
        core_engine.run_stats["target"] = core_engine.cfg.NORMAL_TARGET_COUNT
        engine.start_normal(args)
        return {"status": "success", "message": "启动成功：已自动识别并开启 [常规量产模式]"}


@router.post("/api/stop")
async def stop_task(token: str = Depends(verify_token)):
    if not engine.is_running(): return {"status": "warning", "message": "当前没有运行的任务"}
    stats = core_engine.run_stats
    elapsed_time = round(time.time() - stats["start_time"], 1) if stats["start_time"] > 0 else 0
    total_attempts = stats["success"] + stats["failed"]
    success_rate = round((stats["success"] / total_attempts * 100), 2) if total_attempts > 0 else 0.0
    avg_time = round(elapsed_time / stats["success"], 1) if stats["success"] > 0 else 0.0
    target_str = stats["target"] if stats["target"] > 0 else "∞"
    template_str = getattr(core_engine.cfg, 'TG_BOT', {}).get("template_stop", "🛑 停止：成功 {success}/{target}")
    pwd_blocked = stats["pwd_blocked"] if stats["pwd_blocked"] > 0 else 0
    phone_blocked = stats["phone_verify"] if stats["phone_verify"] > 0 else 0

    try:
        msg = template_str.format(success_rate=success_rate, success=stats['success'], target=target_str,
                                  failed=stats['failed'], retries=stats['retries'], elapsed_time=elapsed_time,
                                  pwd_blocked=pwd_blocked, phone_verify=phone_blocked, avg_time=avg_time)
    except Exception:
        msg = f"⚠️ TG 模板渲染出错：未知的变量格式。\n请检查配置面板中的模板变量是否正确填写。"

    asyncio.create_task(send_tg_msg_async(msg))
    engine.stop()
    return {"status": "success", "message": "已发送停止指令，正在安全退出..."}


@router.get("/api/stats")
async def get_stats(token: str = Depends(verify_token)):
    stats = core_engine.run_stats
    current_reg_mode = getattr(core_engine.cfg, 'REG_MODE', 'protocol')
    ext_running = bool(current_reg_mode == 'extension' and stats.get("ext_is_running"))
    is_running = engine.is_running() or ext_running

    if is_running:
        elapsed = round(time.time() - stats["start_time"], 1) if stats.get("start_time", 0) > 0 else 0
        stats["_frozen_elapsed"] = elapsed
    else:
        elapsed = stats.get("_frozen_elapsed", 0)

    total_attempts = stats["success"] + stats["failed"]
    success_rate = round((stats["success"] / total_attempts * 100), 2) if total_attempts > 0 else 0.0
    avg_time = round(elapsed / stats["success"], 1) if stats["success"] > 0 else 0.0

    progress_pct = 0
    if stats["target"] > 0:
        progress_pct = min(100, round((stats["success"] / stats["target"]) * 100, 1))
    elif stats["success"] > 0:
        progress_pct = 100

    if current_reg_mode == 'extension':
        current_mode = "插件托管 (古法)"
    else:
        current_mode = "CPA 仓管" if getattr(core_engine.cfg, 'ENABLE_CPA_MODE', False) else (
            "Sub2Api 仓管" if getattr(core_engine.cfg, 'ENABLE_SUB2API_MODE', False) else "常规量产")

    return {
        "success": stats["success"], "failed": stats["failed"], "retries": stats["retries"],
        "pwd_blocked": stats.get("pwd_blocked", 0), "phone_verify": stats.get("phone_verify", 0),
        "total": total_attempts, "target": stats["target"] if stats["target"] > 0 else "∞",
        "success_rate": f"{success_rate}%", "elapsed": f"{elapsed}s", "avg_time": f"{avg_time}s",
        "progress_pct": f"{progress_pct}%", "is_running": is_running, "mode": current_mode
    }


@router.post("/api/start_check")
async def start_check_api(token: str = Depends(verify_token)):
    if engine.is_running(): return {"code": 400, "message": "系统正在运行中，请先停止主任务！"}
    default_proxy = getattr(core_engine.cfg, 'DEFAULT_PROXY', None)
    engine.start_check(DummyArgs(proxy=default_proxy if default_proxy else None))
    return {"code": 200, "message": "独立测活指令已下发！"}


@router.get("/api/ext/generate_task")
def ext_generate_task(token: str = Depends(verify_token)):
    from utils.email_providers.mail_service import mask_email, get_email_and_token, clear_sticky_domain
    from utils.register import _generate_password, generate_random_user_info, generate_oauth_url
    import utils.config as cfg_local

    print(f"[{cfg_local.ts()}] [INFO] 正在进行插件古法注册模式，请稍后...")
    try:
        cfg_local.GLOBAL_STOP = False
        clear_sticky_domain()

        email = None
        email_jwt = None
        for _ in range(3):
            print(f"[{cfg_local.ts()}] [INFO] 正在进行邮箱创建...")
            email, email_jwt = get_email_and_token(proxies=None)
            if email:
                break
            time.sleep(1.5)

        if not email:
            return {"status": "error", "message": "邮箱获取超时或暂无库存，请稍候"}

        user_info = generate_random_user_info()
        password = _generate_password()
        oauth_reg = generate_oauth_url()
        print(f"[{cfg_local.ts()}] [INFO] （{mask_email(email)}）下发古法任务数据 (昵称: {user_info['name']})...")

        name_parts = user_info['name'].split(' ')
        return {
            "status": "success",
            "task_data": {
                "email": email,
                "email_jwt": email_jwt,
                "password": password,
                "firstName": name_parts[0] if len(name_parts) > 0 else "John",
                "lastName": name_parts[1] if len(name_parts) > 1 else "Doe",
                "birthday": user_info['birthdate'],
                "registerUrl": oauth_reg.auth_url,
                "code_verifier": oauth_reg.code_verifier,
                "expected_state": oauth_reg.state
            }
        }
    except Exception as e:
        return {"status": "error", "message": f"任务生成失败: {str(e)}"}


@router.get("/api/ext/get_mail_code")
def ext_get_mail_code(email: str, email_jwt: str = "", type: str = "signup", max_attempts: int = 20, token: str = Depends(verify_token)):
    from utils.email_providers.mail_service import get_oai_code
    try:
        code = get_oai_code(email, jwt=email_jwt, proxies=None, max_attempts=max_attempts)
        if code:
            return {"status": "success", "code": code}
        return {"status": "pending"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/api/ext/submit_result")
def ext_submit_result(req: ExtResultReq, token: str = Depends(verify_token)):
    from utils.register import submit_callback_url

    if req.status == "success":
        token_json = req.token_data
        if not token_json and req.callback_url:
            try:
                token_json = submit_callback_url(
                    callback_url=req.callback_url,
                    expected_state=req.expected_state or "",
                    code_verifier=req.code_verifier or ""
                )
            except Exception as e:
                print(f"[{core_engine.ts()}] [ERROR] 古法模式换取 Token 失败: {e}")
                return {"status": "error", "message": "Token 换取失败"}

        if not token_json:
            return {"status": "error", "message": "插件未返回有效 Token 数据"}

        db_manager.save_account_to_db(req.email, req.password, token_json)
        core_engine.run_stats['success'] = core_engine.run_stats.get('success', 0) + 1
        return {"status": "success", "message": "战利品已入库"}

    core_engine.run_stats['failed'] = core_engine.run_stats.get('failed', 0) + 1
    if req.error_type == 'phone_verify':
        core_engine.run_stats['phone_verify'] = core_engine.run_stats.get('phone_verify', 0) + 1
    elif req.error_type == 'pwd_blocked':
        core_engine.run_stats['pwd_blocked'] = core_engine.run_stats.get('pwd_blocked', 0) + 1
    return {"status": "success", "message": "异常统计已录入看板"}


@router.post("/api/ext/heartbeat")
def ext_heartbeat(worker_id: str, token: str = Depends(verify_token)):
    worker_status[worker_id] = time.time()
    return {"status": "success", "message": "ok"}


@router.get("/api/ext/check_node")
def check_node_status(worker_id: str, token: str = Depends(verify_token)):
    last_seen = worker_status.get(worker_id)
    if not last_seen:
        return {"status": "success", "online": False, "reason": "never_connected"}
    is_online = (time.time() - last_seen) < 15
    return {"status": "success", "online": is_online, "last_seen": last_seen}


@router.post("/api/ext/reset_stats")
def ext_reset_stats(token: str = Depends(verify_token)):
    core_engine.run_stats.update({
        "success": 0,
        "failed": 0,
        "retries": 0,
        "pwd_blocked": 0,
        "phone_verify": 0,
        "start_time": time.time(),
        "target": getattr(core_engine.cfg, 'NORMAL_TARGET_COUNT', 0),
        "ext_is_running": True
    })
    return {"status": "success"}


@router.post("/api/ext/stop")
def ext_stop(token: str = Depends(verify_token)):
    core_engine.run_stats["ext_is_running"] = False
    return {"status": "success"}


@router.post("/api/system/restart")
async def restart_system(token: str = Depends(verify_token)):
    try:
        if engine.is_running(): engine.stop()

        def _do_restart():
            time.sleep(1.5)
            print(f"[{core_engine.ts()}] [系统] 🔄 正在执行重启命令...")
            try:
                sys.stdout.flush()
                sys.stderr.flush()
                subprocess.Popen([sys.executable] + sys.argv)
                os._exit(0)
            except Exception as e:
                print(f"[{core_engine.ts()}] [系统] ❌ 重启失败: {e}")
                os._exit(1)

        threading.Thread(target=_do_restart, daemon=True).start()
        return {"status": "success", "message": "指令已下发，系统即将重启..."}
    except Exception as e:
        return {"status": "error", "message": f"重启异常: {str(e)}"}

@router.get("/api/config")
async def get_config(token: str = Depends(verify_token)):
    config_data = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f) or {}
    if isinstance(config_data.get("sub2api_mode"), dict):
        config_data["sub2api_mode"].pop("min_remaining_weekly_percent", None)
    config_data["web_password"] = config_data.get("web_password", "admin")
    if "local_microsoft" not in config_data:
        config_data["local_microsoft"] = {
            "enable_fission": False,
            "master_email": "",
            "client_id": "",
            "refresh_token": "",
            "pool_fission": False
        }
    config_data["http_dynamic_proxy_runtime"] = _build_http_dynamic_proxy_runtime()
    return config_data


@router.post("/api/config")
async def save_config(new_config: dict, token: str = Depends(verify_token)):
    try:
        new_config.pop("http_dynamic_proxy_runtime", None)
        current_config = {}
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    current_config = yaml.safe_load(f) or {}
            except Exception:
                current_config = {}
        if isinstance(new_config.get("sub2api_mode"), dict):
            new_config["sub2api_mode"].pop("min_remaining_weekly_percent", None)
        if "default_proxy" in new_config:
            new_config["default_proxy"] = _normalize_proxy_input_for_save(new_config.get("default_proxy", ""))
        http_dynamic_proxy = new_config.get("http_dynamic_proxy")
        if isinstance(http_dynamic_proxy, dict):
            try:
                http_dynamic_proxy["pool_size"] = max(1, int(http_dynamic_proxy.get("pool_size", 1) or 1))
            except Exception:
                http_dynamic_proxy["pool_size"] = 1
            normalized_dynamic_list = _normalize_proxy_input_list_for_save(http_dynamic_proxy.get("proxy_list", []))
            http_dynamic_proxy["proxy_list"] = normalized_dynamic_list
            if bool(http_dynamic_proxy.get("enable", False)) and not normalized_dynamic_list and not str(new_config.get("default_proxy", "") or "").strip():
                return {"status": "error", "message": "HTTP 动态代理池已开启，但动态代理列表为空且全局默认代理也为空，请至少填写一项。"}
        clash_proxy_pool = new_config.get("clash_proxy_pool")
        http_dynamic_proxy = new_config.get("http_dynamic_proxy")
        auto_notes = []
        if isinstance(clash_proxy_pool, dict) and isinstance(http_dynamic_proxy, dict):
            old_clash = current_config.get("clash_proxy_pool", {}) if isinstance(current_config.get("clash_proxy_pool", {}), dict) else {}
            old_http = current_config.get("http_dynamic_proxy", {}) if isinstance(current_config.get("http_dynamic_proxy", {}), dict) else {}

            old_clash_active = bool(old_clash.get("enable", False))
            new_clash_active = bool(clash_proxy_pool.get("enable", False))
            old_http_active = bool(old_http.get("enable", False))
            new_http_active = bool(http_dynamic_proxy.get("enable", False))

            clash_just_enabled = new_clash_active and not old_clash_active
            http_just_enabled = new_http_active and not old_http_active

            if clash_just_enabled and new_http_active:
                http_dynamic_proxy["enable"] = False
                auto_notes.append("已自动关闭 HTTP 动态代理池")
            elif http_just_enabled and new_clash_active:
                clash_proxy_pool["enable"] = False
                auto_notes.append("已自动关闭 Clash 智能切点")

        with core_engine.cfg.CONFIG_FILE_LOCK:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                yaml.dump(new_config, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
        try:
            reload_all_configs()
        except Exception:
            pass
        final_message = "✅ 配置已成功保存！"
        if auto_notes:
            final_message += "（" + "；".join(auto_notes) + "）"
        return {"status": "success", "message": final_message}
    except Exception as e:
        return {"status": "error", "message": f"❌ 保存失败: {str(e)}"}


@router.get("/api/clash_pool/info")
def get_clash_pool_info(token: str = Depends(verify_token)):
    """返回当前 Clash 订阅、自助更新状态和实际探测到的策略组。"""
    try:
        env_map = _read_clash_pool_env()
        group_candidates, group_error = _get_clash_pool_group_candidates(env_map)
        runtime_status, runtime_error = _inspect_clash_pool_runtime(env_map)
        return {
            "status": "success",
            "data": {
                "sub_url": env_map.get("SUB_URL", ""),
                "effective_sub_url": env_map.get("SUB_URL", ""),
                "count": env_map.get("COUNT", ""),
                "image": env_map.get("IMAGE", ""),
                "status_output": _get_clash_pool_status_output(),
                "group_candidates": group_candidates,
                "group_error": group_error,
                "runtime_status": runtime_status,
                "runtime_error": runtime_error,
            }
        }
    except Exception as e:
        return {"status": "error", "message": f"读取 Clash 订阅信息失败: {e}"}


@router.post("/api/clash_pool/update_subscription")
def update_clash_pool_subscription(req: ClashPoolUpdateReq, token: str = Depends(verify_token)):
    """更新订阅链接并执行代理池刷新脚本。"""
    try:
        sub_url = _sanitize_clash_sub_url(req.sub_url)
        if not sub_url:
            return {"status": "error", "message": "订阅链接不能为空"}
        if not os.path.exists(CLASH_POOL_UPDATE_SCRIPT):
            return {"status": "error", "message": f"未找到更新脚本: {CLASH_POOL_UPDATE_SCRIPT}"}

        resolved_probe, probe_history = _resolve_clash_sub_url(sub_url)
        if not resolved_probe:
            reason = "；".join(
                f"{item.get('url')} -> {item.get('reason') or '失败'}"
                for item in probe_history
            ) or "未找到可用的 Mihomo/Clash 订阅入口"
            return {
                "status": "error",
                "message": f"订阅探测失败：{reason}",
                "probe_history": probe_history,
            }

        effective_sub_url = str(resolved_probe.get("url") or sub_url).strip()
        env_map = _read_clash_pool_env()
        previous_env = dict(env_map)
        env_map["SUB_URL"] = effective_sub_url
        _write_clash_pool_env(env_map)

        code, output = _run_clash_pool_script(CLASH_POOL_UPDATE_SCRIPT, timeout=420)
        tail_lines = "\n".join((output or "").strip().splitlines()[-80:])
        status_output = _get_clash_pool_status_output()
        group_candidates, group_error = _get_clash_pool_group_candidates(env_map)
        assigned_nodes, assign_error = _spread_clash_pool_nodes(env_map)

        should_rollback = bool(code != 0 or (not assigned_nodes and assign_error))
        actual_group_name = next((str(item.get("group") or "").strip() for item in assigned_nodes if str(item.get("group") or "").strip()), "")
        group_sync = {"updated": False, "before": "", "after": ""}

        rollback_output = ""
        rollback_code = None
        if should_rollback:
            try:
                rollback_code, rollback_output = _rollback_clash_pool_update(previous_env)
            except Exception as rollback_error:
                rollback_output = f"自动回滚失败: {rollback_error}"
        elif actual_group_name:
            group_sync = _sync_clash_group_name(actual_group_name)

        if code != 0:
            current_env = _read_clash_pool_env()
            runtime_status, runtime_error = _inspect_clash_pool_runtime(current_env)
            message = f"订阅已写入，但更新脚本执行失败 (exit={code})"
            if rollback_code is not None:
                if rollback_code == 0:
                    message += "；已自动回滚到上一条可用订阅"
                else:
                    message += f"；自动回滚失败 (exit={rollback_code})"
            return {
                "status": "error",
                "message": message,
                "output": tail_lines,
                "status_output": status_output,
                "group_candidates": group_candidates,
                "group_error": group_error,
                "assigned_nodes": assigned_nodes,
                "assign_error": assign_error,
                "probe_history": probe_history,
                "rollback_output": rollback_output[-4000:] if rollback_output else "",
                "runtime_status": runtime_status,
                "runtime_error": runtime_error,
                "data": {
                    "sub_url": current_env.get("SUB_URL", ""),
                    "effective_sub_url": effective_sub_url,
                    "auto_fixed": effective_sub_url != sub_url,
                }
            }

        if not assigned_nodes and assign_error:
            current_env = _read_clash_pool_env()
            runtime_status, runtime_error = _inspect_clash_pool_runtime(current_env)
            message = f"订阅更新后未能完成策略组校验：{assign_error}"
            if rollback_code is not None:
                if rollback_code == 0:
                    message += "；已自动回滚到上一条可用订阅"
                else:
                    message += f"；自动回滚失败 (exit={rollback_code})"
            return {
                "status": "error",
                "message": message,
                "output": tail_lines,
                "status_output": status_output,
                "group_candidates": group_candidates,
                "group_error": group_error,
                "assigned_nodes": assigned_nodes,
                "assign_error": assign_error,
                "probe_history": probe_history,
                "rollback_output": rollback_output[-4000:] if rollback_output else "",
                "runtime_status": runtime_status,
                "runtime_error": runtime_error,
                "data": {
                    "sub_url": current_env.get("SUB_URL", ""),
                    "effective_sub_url": effective_sub_url,
                    "auto_fixed": effective_sub_url != sub_url,
                }
            }

        runtime_status, runtime_error = _inspect_clash_pool_runtime(env_map)
        final_message = "✅ Clash 订阅已更新并重载代理池！"
        if effective_sub_url != sub_url:
            final_message += "（已自动修正为可用的 Mihomo 订阅入口）"
        if group_sync.get("updated"):
            final_message += f"（策略组已自动同步为 {group_sync.get('after')}）"
        if assign_error:
            final_message += f"（节点分流未完全成功：{assign_error}）"
        elif assigned_nodes:
            final_message += "（已自动为各实例分配不同节点）"
        return {
            "status": "success",
            "message": final_message,
            "output": tail_lines,
            "status_output": status_output,
            "group_candidates": group_candidates,
            "group_error": group_error,
            "assigned_nodes": assigned_nodes,
            "assign_error": assign_error,
            "probe_history": probe_history,
            "group_sync": group_sync,
            "runtime_status": runtime_status,
            "runtime_error": runtime_error,
            "data": {
                "sub_url": effective_sub_url,
                "effective_sub_url": effective_sub_url,
                "auto_fixed": effective_sub_url != sub_url,
                "count": env_map.get("COUNT", ""),
                "image": env_map.get("IMAGE", ""),
            }
        }
    except subprocess.TimeoutExpired as e:
        partial = ((e.stdout or "") + "\n" + (e.stderr or "")).strip()
        return {"status": "error", "message": "更新脚本执行超时", "output": partial[-4000:]}
    except Exception as e:
        return {"status": "error", "message": f"Clash 订阅更新失败: {e}"}


@router.post("/api/config/add_wildcard_dns")
async def add_wildcard_dns(req: CFSyncExistingReq, token: str = Depends(verify_token)):
    try:
        main_list = [d.strip() for d in req.sub_domains.split(",") if d.strip()]
        if not main_list: return {"status": "error", "message": "❌ 没有找到有效的主域名"}

        proxy_url = getattr(core_engine.cfg, 'DEFAULT_PROXY', None)
        headers = {"X-Auth-Email": req.api_email, "X-Auth-Key": req.api_key, "Content-Type": "application/json"}
        client_kwargs = {"timeout": 30.0}
        if proxy_url: client_kwargs["proxy"] = proxy_url

        semaphore = asyncio.Semaphore(2)

        async def process_single_domain(client, domain):
            async with semaphore:
                try:
                    zone_resp = await client.get(f"https://api.cloudflare.com/client/v4/zones?name={domain}",
                                                 headers=headers)
                    zone_data = zone_resp.json()
                    if not zone_data.get("success") or not zone_data.get("result"): return False
                    zone_id = zone_data["result"][0]["id"]

                    records = [
                        {"type": "MX", "name": "*", "content": "route3.mx.cloudflare.net", "priority": 36, "ttl": 300},
                        {"type": "MX", "name": "*", "content": "route2.mx.cloudflare.net", "priority": 25, "ttl": 300},
                        {"type": "MX", "name": "*", "content": "route1.mx.cloudflare.net", "priority": 51, "ttl": 300},
                        {"type": "TXT", "name": "*", "content": '"v=spf1 include:_spf.mx.cloudflare.net ~all"',
                         "ttl": 300}
                    ]
                    for rec in records:
                        rec_resp = await client.post(
                            f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records", headers=headers,
                            json=rec)
                    return True
                except:
                    return False
                finally:
                    await asyncio.sleep(0.5)

        async with httpx.AsyncClient(**client_kwargs) as client:
            tasks = [process_single_domain(client, dom) for dom in main_list]
            results = await asyncio.gather(*tasks)

        success_count = sum(1 for r in results if r)
        return {"status": "success", "message": f"成功处理 {success_count}/{len(main_list)} 个域名。"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/api/config/cf_global_status")
def get_cf_global_status(main_domain: str, token: str = Depends(verify_token)):
    try:
        cf_cfg = getattr(core_engine.cfg, '_c', {})
        api_email, api_key = cf_cfg.get("cf_api_email"), cf_cfg.get("cf_api_key")
        if not api_email or not api_key: return {"status": "error", "message": "未配置 CF 账号信息"}

        cf = Cloudflare(api_email=api_email, api_key=api_key)
        domains = [d.strip() for d in main_domain.split(",") if d.strip()]
        results = []

        for dom in domains:
            zones = cf.zones.list(name=dom)
            if not zones.result:
                results.append({"domain": dom, "is_enabled": False, "dns_status": "not_found"})
                continue
            zone_id = zones.result[0].id
            routing_info = cf.email_routing.get(zone_id=zone_id)

            def safe_get(obj, attr, default=None):
                val = getattr(obj, attr, None)
                if val is None and hasattr(obj, 'result'): val = getattr(obj.result, attr, None)
                return val if val is not None else default

            raw_status, raw_synced = safe_get(routing_info, 'status', 'unknown'), safe_get(routing_info, 'synced',
                                                                                           False)
            results.append({"domain": dom, "is_enabled": (raw_status == 'ready' and raw_synced is True),
                            "dns_status": "active" if raw_synced else "pending"})

        return {"status": "success", "data": results}
    except Exception as e:
        return {"status": "error", "message": f"状态同步失败: {str(e)}"}

@router.get("/api/accounts")
async def get_accounts(page: int = Query(1), page_size: int = Query(50), token: str = Depends(verify_token)):
    result = db_manager.get_accounts_page(page, page_size)
    return {"status": "success", "data": result["data"], "total": result["total"], "page": page, "page_size": page_size}


@router.post("/api/accounts/export_selected")
async def export_selected_accounts(req: ExportReq, token: str = Depends(verify_token)):
    if not req.emails: return {"status": "error", "message": "未收到任何要导出的账号"}
    tokens = db_manager.get_tokens_by_emails(req.emails)
    return {"status": "success", "data": tokens} if tokens else {"status": "error", "message": "未能提取到选中账号的有效 Token"}


@router.post("/api/accounts/delete")
async def delete_selected_accounts(req: DeleteReq, token: str = Depends(verify_token)):
    if not req.emails: return {"status": "error", "message": "未收到任何要删除的账号"}
    return {"status": "success", "message": f"成功删除 {len(req.emails)} 个账号"} if db_manager.delete_accounts_by_emails(
        req.emails) else {"status": "error", "message": "删除操作失败"}


@router.post("/api/account/action")
def account_action(data: dict, token: str = Depends(verify_token)):
    try:
        email, action = data.get("email"), data.get("action")
        config = getattr(core_engine.cfg, '_c', {})
        token_data = db_manager.get_token_by_email(email)
        if not token_data: return {"status": "error", "message": f"未找到 {email} 的 Token。"}

        if action == "push":
            if not config.get("cpa_mode", {}).get("enable", False): return {"status": "error",
                                                                            "message": "🚫 推送失败：未开启 CPA 模式！"}
            success, msg = core_engine.upload_to_cpa_integrated(token_data,
                                                                config.get("cpa_mode", {}).get("api_url", ""),
                                                                config.get("cpa_mode", {}).get("api_token", ""))
            return {"status": "success", "message": f"账号 {email} 已成功推送到 CPA！"} if success else {"status": "error",
                                                                                                "message": f"CPA 推送失败: {msg}"}

        elif action == "push_sub2api":
            if not getattr(core_engine.cfg, 'ENABLE_SUB2API_MODE', False): return {"status": "error",
                                                                                   "message": "🚫 推送失败：未开启 Sub2API 模式！"}
            client = Sub2APIClient(api_url=getattr(core_engine.cfg, 'SUB2API_URL', ''),
                                   api_key=getattr(core_engine.cfg, 'SUB2API_KEY', ''))
            success, resp = client.add_account(token_data)
            return {"status": "success", "message": f"账号 {email} 已同步至 Sub2API！"} if success else {"status": "error",
                                                                                                  "message": f"Sub2API 推送失败: {resp}"}
    except Exception as e:
        return {"status": "error", "message": f"后端推送异常: {str(e)}"}


@router.post("/api/accounts/export_sub2api")
async def export_sub2api_accounts(req: ExportReq, token: str = Depends(verify_token)):
    from datetime import datetime, timezone
    try:
        tokens = db_manager.get_tokens_by_emails(req.emails)
        if not tokens: return {"status": "error", "message": "未提取到Token"}

        sub2api_settings = getattr(core_engine.cfg, '_c', {}).get("sub2api_mode", {})
        accounts_list = []
        for td in tokens:
            accounts_list.append({
                "name": str(td.get("email", "unknown"))[:64],
                "platform": "openai", "type": "oauth",
                "credentials": {"refresh_token": td.get("refresh_token", "")},
                "concurrency": int(sub2api_settings.get("account_concurrency", 10)),
                "priority": int(sub2api_settings.get("account_priority", 1)),
                "rate_multiplier": float(sub2api_settings.get("account_rate_multiplier", 1.0)),
                "extra": {"load_factor": int(sub2api_settings.get("account_load_factor", 10))}
            })
        return {"status": "success",
                "data": {"exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "proxies": [],
                         "accounts": accounts_list}}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/api/cloud/accounts")
def get_cloud_accounts(types: str = "sub2api,cpa", page: int = Query(1), page_size: int = Query(50),
                       token: str = Depends(verify_token)):
    type_list = types.split(",")
    combined_data = []
    try:
        if "sub2api" in type_list and getattr(cfg, 'SUB2API_URL', None) and getattr(cfg, 'SUB2API_KEY', None):
            client = Sub2APIClient(api_url=cfg.SUB2API_URL, api_key=cfg.SUB2API_KEY)
            success, raw_sub2_data = client.get_all_accounts()
            if success:
                for item in raw_sub2_data:
                    raw_time = item.get("updated_at", "-")
                    if raw_time != "-":
                        try:
                            raw_time = raw_time.split(".")[0].replace("T", " ")
                        except:
                            pass
                    extra = item.get("extra", {})
                    combined_data.append({
                        "id": str(item.get("id", "")), "account_type": "sub2api",
                        "credential": item.get("name", "未知账号"),
                        "status": "disabled" if item.get("status") == "inactive" else (
                            "active" if item.get("status") == "active" else "dead"),
                        "last_check": raw_time,
                        "details": {"plan_type": item.get("credentials", {}).get("plan_type", "未知"),
                                    "codex_5h_used_percent": extra.get("codex_5h_used_percent", 0),
                                    "codex_7d_used_percent": extra.get("codex_7d_used_percent", 0)}
                    })

        if "cpa" in type_list and getattr(cfg, 'CPA_API_URL', None) and getattr(cfg, 'CPA_API_TOKEN', None):
            from curl_cffi import requests
            res = requests.get(core_engine._normalize_cpa_auth_files_url(cfg.CPA_API_URL),
                               headers={"Authorization": f"Bearer {cfg.CPA_API_TOKEN}"}, timeout=20,
                               impersonate="chrome110")
            if res.status_code == 200:
                for item in [f for f in res.json().get("files", []) if
                             "codex" in str(f.get("type", "")).lower() or "codex" in str(
                                     f.get("provider", "")).lower()]:
                    combined_data.append({"id": item.get("name", ""), "account_type": "cpa",
                                          "credential": item.get("name", "").replace(".json", ""),
                                          "status": "disabled" if item.get("disabled", False) else "active",
                                          "details": {}, "last_check": "-"})

        return {"status": "success", "data": combined_data[(page - 1) * page_size: page * page_size],
                "total": len(combined_data)}
    except Exception as e:
        return {"status": "error", "message": f"拉取远端数据失败: {str(e)}"}


@router.post("/api/cloud/action")
def process_cloud_action(req: CloudActionReq, token: str = Depends(verify_token)):
    from curl_cffi import requests
    from concurrent.futures import ThreadPoolExecutor

    success_count, fail_count, updated_details_map = 0, 0, {}
    sub2api_client = Sub2APIClient(api_url=cfg.SUB2API_URL, api_key=cfg.SUB2API_KEY) if getattr(cfg, 'SUB2API_URL',
                                                                                                None) and getattr(cfg,
                                                                                                                  'SUB2API_KEY',
                                                                                                                  None) else None

    cpa_files_map = {}
    if any(a.type == "cpa" for a in req.accounts) and req.action == "check" and getattr(cfg, 'CPA_API_URL', None):
        try:
            res = requests.get(core_engine._normalize_cpa_auth_files_url(cfg.CPA_API_URL),
                               headers={"Authorization": f"Bearer {cfg.CPA_API_TOKEN}"}, timeout=15,
                               impersonate="chrome110")
            if res.status_code == 200: cpa_files_map = {f.get("name"): f for f in res.json().get("files", [])}
        except:
            pass

    def _worker(acc: CloudAccountItem):
        is_success, details = False, None
        try:
            if acc.type == "sub2api" and sub2api_client:
                if req.action == "check":
                    result, _ = sub2api_client.test_account(acc.id)
                    is_success = (result == "ok")
                    if not is_success: sub2api_client.set_account_status(acc.id, disabled=True)
                elif req.action in ["enable", "disable"]:
                    is_success = sub2api_client.set_account_status(acc.id, disabled=(req.action == "disable"))
                elif req.action == "delete":
                    is_success, _ = sub2api_client.delete_account(acc.id)

            elif acc.type == "cpa" and getattr(cfg, 'CPA_API_URL', None):
                if req.action == "check":
                    item = cpa_files_map.get(acc.id, {"name": acc.id, "disabled": False})
                    is_success, _ = core_engine.test_cliproxy_auth_file(item, cfg.CPA_API_URL, cfg.CPA_API_TOKEN)
                    if '_raw_usage' in item: details = parse_cpa_usage_to_details(item['_raw_usage'])
                    if not is_success: core_engine.set_cpa_auth_file_status(cfg.CPA_API_URL, cfg.CPA_API_TOKEN, acc.id,
                                                                            disabled=True)
                elif req.action in ["enable", "disable"]:
                    is_success = core_engine.set_cpa_auth_file_status(cfg.CPA_API_URL, cfg.CPA_API_TOKEN, acc.id,
                                                                      disabled=(req.action == "disable"))
                elif req.action == "delete":
                    is_success = requests.delete(core_engine._normalize_cpa_auth_files_url(cfg.CPA_API_URL),
                                                 headers={"Authorization": f"Bearer {cfg.CPA_API_TOKEN}"},
                                                 params={"name": acc.id}, impersonate="chrome110").status_code in (
                                 200, 204)
        except:
            pass
        return (is_success, acc.id, details)

    target_threads = 5
    if any(a.type == "cpa" for a in req.accounts): target_threads = max(target_threads, int(
        getattr(cfg, '_c', {}).get('cpa_mode', {}).get('threads', 10)))
    if any(a.type == "sub2api" for a in req.accounts): target_threads = max(target_threads, int(
        getattr(cfg, '_c', {}).get('sub2api_mode', {}).get('threads', 10)))

    with ThreadPoolExecutor(max_workers=max(1, min(target_threads, 50))) as executor:
        for is_success, acc_id, details in executor.map(_worker, req.accounts):
            if is_success:
                success_count += 1
            else:
                fail_count += 1
            if details: updated_details_map[acc_id] = details

    msg = f"测活完毕 | 存活: {success_count} 个 | 失效并已自动禁用: {fail_count} 个" if req.action == "check" else f"指令已下发 | 成功: {success_count} 个 | 失败: {fail_count} 个"
    return {"status": "success" if fail_count == 0 else "warning", "message": msg,
            "updated_details": updated_details_map}

@router.get('/api/sms/balance')
def api_get_sms_balance(token: str = Depends(verify_token)):
    from utils.integrations.hero_sms import hero_sms_get_balance
    proxy_url = core_engine.cfg.DEFAULT_PROXY
    balance, err = hero_sms_get_balance(proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None)
    return {"status": "success", "balance": f"{balance:.2f}"} if balance >= 0 else {"status": "error", "message": err}


@router.post('/api/sms/prices')
def api_get_sms_prices(req: SMSPriceReq, token: str = Depends(verify_token)):
    from utils.integrations.hero_sms import _hero_sms_prices_by_service
    proxy_url = core_engine.cfg.DEFAULT_PROXY
    rows = _hero_sms_prices_by_service(req.service,
                                       proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None)
    return {"status": "success", "prices": rows} if rows else {"status": "error", "message": "无法获取价格或当前服务无库存"}


@router.post("/api/luckmail/bulk_buy")
def api_luckmail_bulk_buy(req: LuckMailBulkBuyReq, token: str = Depends(verify_token)):
    try:
        from utils.email_providers.luckmail_service import LuckMailService
        lm_service = LuckMailService(api_key=req.config.get("api_key"),
                                     preferred_domain=req.config.get("preferred_domain", ""),
                                     email_type=req.config.get("email_type", "ms_graph"),
                                     variant_mode=req.config.get("variant_mode", ""))
        tag_id = req.config.get("tag_id") or lm_service.get_or_create_tag_id("已使用")
        results = lm_service.bulk_purchase(quantity=req.quantity, auto_tag=req.auto_tag, tag_id=tag_id)
        return {"status": "success", "message": f"成功购买 {len(results)} 个邮箱！", "data": results}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/api/gmail/auth_url")
async def get_gmail_auth_url(token: str = Depends(verify_token)):
    if not os.path.exists(GMAIL_CLIENT_SECRETS): return {"status": "error",
                                                         "message": f"❌ 未找到凭证文件！请上传至: {GMAIL_CLIENT_SECRETS}"}
    try:
        url, verifier = GmailOAuthHandler.get_authorization_url(GMAIL_CLIENT_SECRETS)
        with open(GMAIL_VERIFIER_PATH, "w") as f:
            f.write(verifier)
        return {"status": "success", "url": url}
    except Exception as e:
        return {"status": "error", "message": f"生成链接失败: {str(e)}"}


@router.post("/api/gmail/exchange_code")
async def exchange_gmail_code(req: GmailExchangeReq, token: str = Depends(verify_token)):
    if not req.code: return {"status": "error", "message": "授权码不能为空"}
    try:
        if not os.path.exists(GMAIL_VERIFIER_PATH): return {"status": "error", "message": "会话已过期，请重新生成链接"}
        with open(GMAIL_VERIFIER_PATH, "r") as f:
            stored_verifier = f.read().strip()
        success, msg = GmailOAuthHandler.save_token_from_code(GMAIL_CLIENT_SECRETS, req.code, GMAIL_TOKEN_PATH,
                                                              code_verifier=stored_verifier,
                                                              proxy=getattr(core_engine.cfg, 'DEFAULT_PROXY', None))
        if success and os.path.exists(GMAIL_VERIFIER_PATH):
            os.remove(GMAIL_VERIFIER_PATH)
            return {"status": "success", "message": "✨ 授权成功！token.json 已保存在 data 目录。"}
        return {"status": "error", "message": msg}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/api/sub2api/groups")
def get_sub2api_groups(token: str = Depends(verify_token)):
    from curl_cffi import requests as cffi_requests
    sub2api_url = getattr(core_engine.cfg, "SUB2API_URL", "").strip()
    sub2api_key = getattr(core_engine.cfg, "SUB2API_KEY", "").strip()
    if not sub2api_url or not sub2api_key: return {"status": "error",
                                                   "message": "Please save the Sub2API URL and API key first."}
    try:
        response = cffi_requests.get(f"{sub2api_url.rstrip('/')}/api/v1/admin/groups/all",
                                     headers={"x-api-key": sub2api_key, "Content-Type": "application/json"}, timeout=10,
                                     impersonate="chrome110")
        if response.status_code != 200: return {"status": "error",
                                                "message": f"HTTP {response.status_code}: {response.text[:200]}"}
        return {"status": "success", "data": response.json().get("data", [])}
    except Exception as exc:
        return {"status": "error", "message": f"Failed to fetch Sub2API groups: {exc}"}


@router.get("/api/system/check_update")
async def check_update(current_version: str, token: str = Depends(verify_token)):
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get("https://api.github.com/repos/wenfxl/openai-cpa/releases/latest",
                                    headers={"Accept": "application/vnd.github.v3+json"})
            if resp.status_code != 200: return {"status": "error",
                                                "message": f"无法获取更新数据 (GitHub API 返回 HTTP {resp.status_code})"}
        data = resp.json()
        remote_version = data.get("tag_name", "")

        def _parse(v):
            return [int(x) for x in re.findall(r'\d+', str(v))]

        has_update = _parse(remote_version) > _parse(current_version) if remote_version else False
        assets = data.get("assets")
        download_url = assets[0].get("browser_download_url", "") if assets else data.get("zipball_url", "")
        return {"status": "success", "has_update": has_update, "remote_version": remote_version,
                "changelog": data.get("body", "无更新日志"), "download_url": download_url,
                "html_url": data.get("html_url", "")}
    except Exception as e:
        return {"status": "error", "message": f"检查更新发生未知异常: {str(e)}"}

@router.post("/api/logs/clear")
async def clear_backend_logs(token: str = Depends(verify_token)):
    log_history.clear()
    return {"status": "success"}


@router.get("/api/logs/stream")
async def stream_logs(request: Request, token: str = Query(None)):
    if token not in VALID_TOKENS: raise HTTPException(status_code=401, detail="Unauthorized")

    async def log_generator():
        current_snapshot = list(log_history)
        for old_msg in current_snapshot:
            yield f"data: {old_msg}\n\n"
        last_sent_msg = current_snapshot[-1] if current_snapshot else None
        idle_loops = 0

        try:
            while True:
                if await request.is_disconnected():
                    break
                snap = list(log_history)
                if snap and snap[-1] != last_sent_msg:
                    start_idx = 0
                    for i in range(len(snap) - 1, -1, -1):
                        if snap[i] == last_sent_msg:
                            start_idx = i + 1
                            break
                    for i in range(start_idx, len(snap)):
                        yield f"data: {snap[i]}\n\n"
                    last_sent_msg = snap[-1]
                    idle_loops = 0
                else:
                    idle_loops += 1
                    if idle_loops >= 50:
                        yield ": keepalive\n\n"
                        idle_loops = 0

                await asyncio.sleep(0.3)
        except Exception:
            pass

    return StreamingResponse(log_generator(), media_type="text/event-stream")

@router.post("/api/cluster/control")
async def cluster_control(req: ClusterControlReq, token: str = Depends(verify_token)):
    if req.action not in ["start", "stop", "restart", "export_accounts"]: return {"status": "error",
                                                                                  "message": "不支持的指令"}
    with cluster_lock: NODE_COMMANDS[req.node_name] = req.action
    return {"status": "success", "message": f"指令 [{req.action}] 已排队"}


@router.get("/api/cluster/view")
async def cluster_view(token: str = Depends(verify_token)):
    global CLUSTER_NODES
    now = time.time()
    with cluster_lock:
        CLUSTER_NODES = {k: v for k, v in CLUSTER_NODES.items() if now - v["last_seen"] < 20}
        return {"status": "success", "nodes": CLUSTER_NODES}


@router.post("/api/cluster/report")
async def cluster_report(req: ClusterReportReq):
    cf_dict = getattr(core_engine.cfg, '_c', {})
    if req.secret != str(cf_dict.get("cluster_secret", "change-me-cluster-secret")).strip(): return {"status": "error",
                                                                                      "message": "密钥错误"}

    target_cmd = NODE_COMMANDS.get(req.node_name, "none")
    node_is_running = req.stats.get("is_running", False)

    if target_cmd in ["restart", "export_accounts"]:
        NODE_COMMANDS[req.node_name] = "none"
    elif (target_cmd == "start" and node_is_running) or (target_cmd == "stop" and not node_is_running):
        NODE_COMMANDS[req.node_name] = "none"
        target_cmd = "none"

    with cluster_lock:
        CLUSTER_NODES[req.node_name] = {
            "stats": req.stats, "logs": req.logs, "last_seen": time.time(),
            "join_time": CLUSTER_NODES.get(req.node_name, {}).get("join_time", time.time())
        }
    return {"status": "success", "command": target_cmd}


@router.websocket("/api/cluster/report_ws")
async def ws_cluster_report(websocket: WebSocket, node_name: str, secret: str):
    await websocket.accept()
    if secret != str(getattr(core_engine.cfg, '_c', {}).get("cluster_secret", "change-me-cluster-secret")).strip():
        await websocket.close(code=1008, reason="Secret Mismatch")
        return
    try:
        while True:
            data = await websocket.receive_json()
            target_cmd = NODE_COMMANDS.get(node_name, "none")
            node_is_running = data.get("stats", {}).get("is_running", False)
            if target_cmd in ["restart", "export_accounts"]:
                NODE_COMMANDS[node_name] = "none"
            elif (target_cmd == "start" and node_is_running) or (target_cmd == "stop" and not node_is_running):
                NODE_COMMANDS[node_name] = "none"
                target_cmd = "none"
            with cluster_lock:
                CLUSTER_NODES[node_name] = {
                    "stats": data.get("stats", {}), "logs": data.get("logs", []), "last_seen": time.time(),
                    "join_time": CLUSTER_NODES.get(node_name, {}).get("join_time", time.time())
                }
            await websocket.send_json({"command": target_cmd})
    except Exception:
        pass


@router.websocket("/api/cluster/view_ws")
async def cluster_view_ws(websocket: WebSocket, token: str = Query(None)):
    if token not in VALID_TOKENS:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    try:
        while True:
            global CLUSTER_NODES
            now = time.time()
            with cluster_lock:
                CLUSTER_NODES = {k: v for k, v in CLUSTER_NODES.items() if now - v["last_seen"] < 20}
                await websocket.send_json({"status": "success", "nodes": CLUSTER_NODES})
            await asyncio.sleep(0.5)
    except Exception:
        pass


@router.post("/api/cluster/upload_accounts")
def cluster_upload_accounts(req: ClusterUploadAccountsReq):
    if req.secret != str(getattr(core_engine.cfg, '_c', {}).get("cluster_secret", "change-me-cluster-secret")).strip(): return {
        "status": "error", "message": "密钥错误"}
    success_count = 0
    for acc in req.accounts:
        if acc.get("email") and acc.get("token_data"):
            if db_manager.save_account_to_db(acc.get("email"), acc.get("password"),
                                             acc.get("token_data")): success_count += 1

    msg = f"[{core_engine.ts()}] [系统] 📦 成功从子控 [{req.node_name}] 提取并完美入库 {success_count} 个账号！"
    print(msg)
    try:
        log_history.append(msg)
    except:
        pass
    return {"status": "success", "message": f"成功接收 {success_count} 个账号"}

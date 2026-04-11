import httpx
import requests
import asyncio
from utils import config as cfg

def _get_tg_config():
    try:
        return {
            "enable": cfg.TG_BOT.get("enable", False),
            "token": cfg.TG_BOT.get("token", ""),
            "chat_id": cfg.TG_BOT.get("chat_id", ""),
            "proxy": getattr(cfg, 'DEFAULT_PROXY', None) if cfg.TG_BOT.get("use_proxy", False) else None
        }
    except Exception:
        return {"enable": False}


async def send_tg_msg_async(text: str):
    tg = _get_tg_config()
    if not tg["enable"] or not tg["token"] or not tg["chat_id"]:
        return

    url = f"https://api.telegram.org/bot{tg['token']}/sendMessage"
    client_kwargs = {"timeout": 10.0}
    if tg["proxy"]:
        client_kwargs["proxy"] = tg["proxy"]

    payload = {
        "chat_id": tg["chat_id"],
        "text": text,
        "parse_mode": "HTML"
    }

    try:
        async with httpx.AsyncClient(**client_kwargs) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                print(f"[{cfg.ts()}] [警告] 异步 TG 通知发送失败: HTTP {resp.status_code} {resp.text[:240]}")
    except Exception as e:
        print(f"[{cfg.ts()}] [警告] 异步 TG 通知发送失败: {e}")


def send_tg_msg_sync(text: str):
    tg = _get_tg_config()
    if not tg["enable"] or not tg["token"] or not tg["chat_id"]:
        return

    url = f"https://api.telegram.org/bot{tg['token']}/sendMessage"
    proxies = {"http": tg["proxy"], "https": tg["proxy"]} if tg["proxy"] else None

    payload = {
        "chat_id": tg["chat_id"],
        "text": text,
        "parse_mode": "HTML"
    }

    try:
        resp = requests.post(url, json=payload, proxies=proxies, timeout=10)
        if resp.status_code != 200:
            print(f"[{cfg.ts()}] [警告] 同步 TG 通知发送失败: HTTP {resp.status_code} {resp.text[:240]}")
    except Exception as e:
        print(f"[{cfg.ts()}] [警告] 同步 TG 通知发送失败: {e}")

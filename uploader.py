#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
uploader.py — standalone Telegram uploader (subprocess pattern)
Input via stdin: JSON {"file":"...","title":"...","caption":"...","cfg":{...}}
"""
import asyncio
import json
import os
import sys
import time


def log(tag, msg):
    print(f"[{tag}] {msg}", flush=True)


def fmt_time(sec):
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h: return f"{h}h {m}m {s}s"
    if m: return f"{m}m {s}s"
    return f"{s}s"


def main():
    raw = sys.stdin.read().strip()
    try:
        data = json.loads(raw)
    except Exception as e:
        log("ERR", f"Invalid JSON: {e}")
        sys.exit(1)

    file_path = data.get("file", "")
    title     = data.get("title", "AniSub")
    caption   = data.get("caption", "")
    cfg       = data.get("cfg", {})

    if not file_path or not os.path.exists(file_path):
        log("ERR", f"File not found: {file_path}")
        sys.exit(1)

    chat_id = cfg.get("tg_chat_id", os.environ.get("CHAT_ID", ""))
    api_id  = cfg.get("tg_api_id",  os.environ.get("TG_API_ID", ""))
    api_hash= cfg.get("tg_api_hash",os.environ.get("TG_API_HASH", ""))
    bot_tok = cfg.get("tg_bot_token",os.environ.get("BOT_TOKEN", ""))

    try:
        chat_id = int(chat_id)
    except Exception:
        pass

    size_mb = os.path.getsize(file_path) / 1048576
    log("UP", f"File: {size_mb:.1f} MB | Title: {title}")

    last = [0.0]

    async def _do():
        from pyrogram import Client
        t0 = time.time()
        async with Client(
            "anisub_upload",
            api_id    = int(api_id),
            api_hash  = api_hash,
            bot_token = bot_tok,
            in_memory = True,
        ) as app:
            def _prog(cur, total):
                if total and time.time() - last[0] > 2:
                    pct = int(cur / total * 100)
                    bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
                    log("UP", f"[{bar}] {pct}%  {cur//1048576}/{total//1048576} MB")
                    last[0] = time.time()

            cap = f"**{title}**\n\n{caption}".strip() if caption else f"**{title}**"
            msg = await app.send_video(
                chat_id            = chat_id,
                video              = file_path,
                caption            = cap,
                supports_streaming = True,
                progress           = _prog,
            )
            elapsed = time.time() - t0
            log("UP", f"Done in {fmt_time(elapsed)}")
            if hasattr(msg, "link") and msg.link:
                log("LINK", msg.link)
            return True

    # Fresh event loop — no conflicts
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_do())
        sys.exit(0)
    except Exception as e:
        log("ERR", str(e))
        sys.exit(1)
    finally:
        loop.close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AniSub Web — Flask backend for Render deployment"""

import json
import logging
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import uuid
import urllib.request
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request, stream_with_context

HOME       = Path.home()
CONFIG_FILE= HOME / ".anisub_config.json"
WORK_DIR   = HOME / "anisub_work"
FONTS_DIR  = HOME / "anisub_fonts"
UPLOAD_DIR = HOME / "anisub_uploads"
BASE_DIR   = Path(__file__).parent

for _d in (WORK_DIR, FONTS_DIR, UPLOAD_DIR):
    _d.mkdir(parents=True, exist_ok=True)

def _check_ffmpeg():
    return [t for t in ("ffmpeg", "ffprobe") if not shutil.which(t)]

sys.path.insert(0, str(BASE_DIR))
import file as _core

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_jobs: dict = {}
_jobs_lock = threading.Lock()


def _load_cfg() -> dict:
    # First try env vars (Render environment variables)
    env_cfg = {}
    if os.environ.get("TG_API_ID"):
        env_cfg["tg_api_id"]    = os.environ["TG_API_ID"]
        env_cfg["tg_api_hash"]  = os.environ.get("TG_API_HASH", "")
        env_cfg["tg_bot_token"] = os.environ.get("BOT_TOKEN", "")
        env_cfg["tg_chat_id"]   = os.environ.get("CHAT_ID", "")
        return env_cfg
    # Fallback to config file
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_cfg(cfg: dict):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def _new_job(job_id, title=""):
    job = {
        "queue":      queue.Queue(),
        "history":    [],
        "status":     "running",
        "title":      title,
        "started_at": time.strftime("%H:%M:%S"),
        "thread":     None,
    }
    with _jobs_lock:
        _jobs[job_id] = job
    return job


def _log(job, level, msg):
    event = {"level": level, "msg": msg, "ts": time.strftime("%H:%M:%S")}
    with _jobs_lock:
        job["history"].append(event)
    job["queue"].put(event)


def _done(job, success, msg=""):
    event = {"level": "done", "success": success, "msg": msg, "ts": time.strftime("%H:%M:%S")}
    with _jobs_lock:
        job["history"].append(event)
        job["status"] = "done" if success else "failed"
    job["queue"].put(event)


@app.route("/config", methods=["GET"])
def get_config():
    cfg = _load_cfg()
    safe = {}
    for k, v in cfg.items():
        if v and len(str(v)) > 6 and k in ("tg_api_hash", "tg_bot_token"):
            safe[k] = str(v)[:4] + "••••" + str(v)[-3:]
        else:
            safe[k] = v
    # Show if env vars are set
    safe["env_mode"] = bool(os.environ.get("TG_API_ID"))
    return jsonify(safe)


@app.route("/config", methods=["POST"])
def post_config():
    data = request.get_json(force=True) or {}
    required = ["tg_api_id", "tg_api_hash", "tg_bot_token", "tg_chat_id"]
    missing = [k for k in required if not str(data.get(k, "")).strip()]
    if missing:
        return jsonify({"error": f"Missing: {', '.join(missing)}"}), 400
    cfg = _load_cfg()
    for k in required:
        cfg[k] = str(data[k]).strip()
    _save_cfg(cfg)
    return jsonify({"ok": True, "msg": "Saved!"})


@app.route("/system")
def system_check():
    missing = _check_ffmpeg()
    return jsonify({
        "ffmpeg":  shutil.which("ffmpeg") or None,
        "ffprobe": shutil.which("ffprobe") or None,
        "missing": missing,
        "ok":      len(missing) == 0,
    })


@app.route("/jobs/active")
def jobs_active():
    with _jobs_lock:
        active = [
            {"job_id": jid, "status": j["status"], "title": j["title"], "started_at": j["started_at"]}
            for jid, j in _jobs.items() if j["status"] == "running"
        ]
    return jsonify(active)


@app.route("/jobs/<job_id>/history")
def job_history(job_id):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        return jsonify({"error": "Not found"}), 404
    return jsonify({
        "status": job["status"], "title": job["title"],
        "started_at": job["started_at"], "history": job["history"],
    })


@app.route("/process", methods=["POST"])
def post_process():
    missing = _check_ffmpeg()
    if missing:
        return jsonify({"error": f"ffmpeg missing: {', '.join(missing)}"}), 500

    cfg = _load_cfg()
    if not all(cfg.get(k) for k in ("tg_api_id", "tg_api_hash", "tg_bot_token", "tg_chat_id")):
        return jsonify({"error": "Telegram config incomplete. Go to Settings."}), 400

    video_url = (request.form.get("video_url") or "").strip()
    referer   = (request.form.get("referer")   or "").strip()
    style     = (request.form.get("style")     or "1").strip()
    title     = (request.form.get("title")     or "AniSub").strip()
    caption   = (request.form.get("caption")   or "").strip()
    sub_file  = request.files.get("sub_file")
    sub_text  = (request.form.get("sub_text")  or "").strip()
    sub_url   = (request.form.get("sub_url")   or "").strip()

    if not video_url:
        return jsonify({"error": "Video URL required."}), 400
    if not (sub_file or sub_text or sub_url):
        return jsonify({"error": "Subtitle required."}), 400
    if style not in ("1", "2", "3"):
        return jsonify({"error": "Style must be 1-3."}), 400

    job_id = str(uuid.uuid4())
    job    = _new_job(job_id, title)

    sub_save_path = None
    if sub_file and sub_file.filename:
        ext = Path(sub_file.filename).suffix.lower() or ".srt"
        sub_save_path = str(UPLOAD_DIR / f"{job_id}{ext}")
        sub_file.save(sub_save_path)
    elif sub_text:
        sub_save_path = str(UPLOAD_DIR / f"{job_id}.srt")
        Path(sub_save_path).write_text(sub_text, encoding="utf-8")

    t = threading.Thread(
        target=_run_job,
        args=(job_id, job, cfg, video_url, referer, sub_save_path or sub_url, style, title, caption),
        daemon=True,
    )
    job["thread"] = t
    t.start()
    return jsonify({"job_id": job_id})


@app.route("/status/<job_id>")
def status_stream(job_id):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        return jsonify({"error": "Not found"}), 404

    with _jobs_lock:
        history_snap = list(job["history"])
        already_done = job["status"] in ("done", "failed")

    q = job["queue"]

    def generate():
        for event in history_snap:
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        if already_done:
            return
        while True:
            try:
                event = q.get(timeout=25)
            except queue.Empty:
                yield 'data: {"level":"ping"}\n\n'
                continue
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            if event.get("level") == "done":
                break

    return Response(stream_with_context(generate()), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/")
def index():
    return render_template("index.html")


def _run_job(job_id, job, cfg, video_url, referer, sub_input, style_key, title, caption):
    def ok(m):   _log(job, "ok",    m)
    def warn(m): _log(job, "warn",  m)
    def err(m):  _log(job, "error", m)
    def info(m): _log(job, "info",  m)
    def step(n, m): _log(job, "step", f"[{n}] {m}")

    if _check_ffmpeg():
        err("ffmpeg not found!")
        _done(job, False, "ffmpeg missing")
        return

    _core.ok = ok; _core.warn = warn; _core.err = err
    _core.info = info; _core.step = step

    try:
        step(1, "Probing video…")
        video_url_r, meta = _core.get_video_meta(video_url, referer)
        play_w   = int(meta.get("width")  or 1280)
        play_h   = int(meta.get("height") or 720)
        duration = meta.get("duration")
        ok(f"Video: {play_w}×{play_h}" + (f"  {_core.fmt_time(duration)}" if duration else ""))

        step(2, "Loading subtitle…")
        work_dir = WORK_DIR / job_id
        work_dir.mkdir(parents=True, exist_ok=True)
        sub_path, sub_fmt = _core.load_subtitle(sub_input, work_dir)

        step(3, f"Style {style_key}…")
        preset    = _core.STYLE_PRESETS[style_key]
        font_meta = _core.FONTS[preset["font_key"]]
        color_hex = _core.COLORS[preset["color_key"]][1]
        align     = _core.POSITIONS[preset["position_key"]][1]
        font_size = _core.calc_font_size(_core.SIZES[preset["size_key"]][1], play_h)
        margin_v  = _core.calc_margin_v(preset["position_key"], play_h, preset)

        step(4, f"Font: {font_meta['name']}…")
        _core.ensure_font(preset["font_key"])

        step(5, "Building ASS…")
        ass_path  = str(work_dir / "subtitle.ass")
        style_cfg = {
            "preset": preset,
            "header": {
                "play_w": play_w, "play_h": play_h,
                "font_family": font_meta["family"], "font_size": font_size,
                "primary_colour": color_hex, "align": align,
                "margin_v": margin_v, "bold": preset["bold"],
                "italic": preset["italic"], "preset": preset,
            },
        }
        if sub_fmt == "srt":
            _core.srt_to_ass(sub_path, ass_path, style_cfg)
        else:
            _core.restyle_ass(sub_path, ass_path, style_cfg)

        step(6, "Rendering…")
        out_path    = str(work_dir / "output.mp4")
        vf          = "ass='" + _core.esc_filter(ass_path) + "':fontsdir='" + _core.esc_filter(str(FONTS_DIR)) + "'"
        headers_val = "Accept: */*\r\n"
        if referer:
            headers_val += f"Referer: {referer}\r\nOrigin: {referer}\r\n"

        cmd = [
            "ffmpeg", "-y",
            "-user_agent", "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36",
            "-headers", headers_val, "-i", video_url_r,
            "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", out_path,
        ]
        rc, render_time = _run_ffmpeg_logged(cmd, duration, job)
        if rc != 0 or not os.path.exists(out_path):
            raise RuntimeError(f"FFmpeg failed (code {rc})")

        size_mb = round(os.path.getsize(out_path) / 1_048_576, 1)
        ok(f"Render done — {size_mb} MB ({_core.fmt_time(render_time)})")

        # ── Upload via subprocess (no event loop conflict) ──
        step(7, f"Uploading {size_mb} MB to Telegram…")
        _t0  = time.time()
        _inp = json.dumps({"file": out_path, "title": title, "caption": caption, "cfg": cfg})
        _proc = subprocess.Popen(
            ["python3", str(BASE_DIR / "uploader.py")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True
        )
        _proc.stdin.write(_inp)
        _proc.stdin.close()
        link = None
        for _line in _proc.stdout:
            _line = _line.strip()
            if not _line: continue
            if _line.startswith("[LINK]"):
                link = _line.split("]", 1)[1].strip()
                ok(f"Telegram link: {link}")
            elif _line.startswith("[ERR]"):
                err(_line)
            else:
                info(_line)
        _proc.wait()
        upload_time = time.time() - _t0

        if _proc.returncode == 0:
            ok(f"Upload done — {_core.fmt_time(upload_time)}")
        else:
            warn("Upload may have failed — check Telegram.")

        shutil.rmtree(work_dir, ignore_errors=True)
        try:
            if sub_input and str(UPLOAD_DIR) in str(sub_input):
                Path(sub_input).unlink(missing_ok=True)
        except Exception:
            pass
        info("Temp files cleaned.")
        _done(job, True, link or "Done!")

    except Exception as exc:
        err(str(exc))
        logger.exception("Job %s failed", job_id)
        shutil.rmtree(WORK_DIR / job_id, ignore_errors=True)
        _done(job, False, str(exc))


def _run_ffmpeg_logged(cmd, duration, job):
    import re
    start    = time.time()
    p        = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, bufsize=1)
    last_pct = -1
    last_t   = 0
    for line in p.stderr:
        line = line.rstrip()
        if not line: continue
        if "time=" in line and duration:
            m = re.search(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)", line)
            if m:
                cur = int(m.group(1))*3600 + int(m.group(2))*60 + float(m.group(3))
                pct = min(99, int(cur / duration * 100))
                if pct != last_pct and time.time() - last_t > 1.0:
                    bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
                    _log(job, "progress", f"[{bar}] {pct}%  elapsed={_core.fmt_time(time.time()-start)}")
                    last_pct = pct
                    last_t   = time.time()
        elif any(x in line.lower() for x in ["error", "failed", "invalid", "no such"]):
            _log(job, "error", line)
    p.wait()
    return p.returncode, time.time() - start


# ── Keep-alive ping ──────────────────────────────────────────────
def _keep_alive():
    time.sleep(60)
    while True:
        try:
            urllib.request.urlopen("http://localhost:10000/system", timeout=10)
        except Exception:
            pass
        time.sleep(270)

threading.Thread(target=_keep_alive, daemon=True).start()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print(f"\n  AniSub Web  →  http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)

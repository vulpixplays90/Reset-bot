#!/usr/bin/env python3
"""
reset_api.py

Flask API to send "password reset" requests using pluggable engines (APIs).
Stores engines and stats in MongoDB.

Environment variables:
- MONGO_URI          (required)   : MongoDB connection string
- ADMIN_API_KEY      (recommended) : admin key for engine management & stats (default: "changeme")
- GLOBAL_COOLDOWN    (optional)   : global cooldown in seconds (default: 10)
- FLASK_ENV / PORT   (optional)   : flask run parameters
"""

import os
import time
import uuid
import random
import string
from functools import wraps
from flask import Flask, request, jsonify, abort
import httpx
from pymongo import MongoClient

# -------------------------
# Configuration
# -------------------------
MONGO_URI = os.environ.get("MONGO_URI") or "mongodb+srv://botplays90:botplays90@botplays.ycka9.mongodb.net/?retryWrites=true&w=majority&appName=botplays"
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "changeme")
GLOBAL_COOLDOWN = float(os.environ.get("GLOBAL_COOLDOWN", 10.0))
HTTP_TIMEOUT = float(os.environ.get("HTTP_TIMEOUT", 10.0))

# -------------------------
# App + DB setup
# -------------------------
app = Flask(__name__)
mongo = MongoClient(MONGO_URI)
db = mongo["reset_api"]
engines_col = db["engines"]           # stores engine documents: {name, url, method, type, active, metadata}
stats_col = db["stats"]               # stores counts, e.g. {"_id":"reset_counter","count":N}
leaderboard_col = db["leaderboard"]   # per requester stats
# (optional) users_col for tracking requesters
users_col = db["users"]

# In-memory global cooldown timestamp (per-process).
# If you want cross-process cooldown, store timestamp in DB instead.
_last_global_reset_ts = 0.0

# -------------------------
# Helpers
# -------------------------
def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        key = request.headers.get("X-API-KEY") or request.args.get("api_key")
        if not key or key != ADMIN_API_KEY:
            return jsonify({"error": "unauthorized"}), 401
        return f(*args, **kwargs)
    return wrapper

def gen_random_values():
    _csrftoken = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    guid = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    # build randomized-ish android user agent similar to original script
    rand9 = lambda n: ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))
    user_agent = (
        f"Instagram 150.0.0.0.000 Android (29/10; 300dpi; 720x1440; "
        f"{rand9(16)}/{rand9(16)}; {rand9(16)}; {rand9(16)}; {rand9(16)}; en_GB;)"
    )
    return _csrftoken, guid, device_id, user_agent

def obfuscate_account(acc: str) -> str:
    if "@" in acc:
        local, domain = acc.split("@", 1)
        if len(local) <= 2:
            masked = local[0] + "*"*(len(local)-1)
        else:
            masked = local[0] + "*"*(len(local)-2) + local[-1]
        return masked + "@" + domain
    # fallback: partially mask username
    if len(acc) <= 2:
        return acc[0] + "*"
    return acc[0] + "*"*(len(acc)-2) + acc[-1]

def increment_stat(counter_name="reset_counter", n=1):
    stats_col.update_one({"_id": counter_name}, {"$inc": {"count": n}}, upsert=True)

def add_leaderboard_entry(requester_id, requester_name, increment=1):
    now_ts = time.time()
    leaderboard_col.update_one(
        {"_id": requester_id},
        {"$inc": {"count": increment}, "$set": {"name": requester_name, "last_reset": now_ts}},
        upsert=True
    )

# -------------------------
# Engine management endpoints
# -------------------------
@app.route("/engines", methods=["POST"])
@require_admin
def add_engine():
    """
    Add a new engine.
    JSON body example:
    {
      "name": "instagram_mobile",
      "url": "https://i.instagram.com/api/v1/accounts/send_password_reset/",
      "method": "POST",
      "type": "instagram_mobile",   # optional, used by the payload builder
      "active": true,
      "metadata": { ... }          # optional
    }
    """
    body = request.get_json(force=True, silent=True)
    if not body:
        return jsonify({"error": "invalid json body"}), 400

    name = body.get("name")
    url = body.get("url")
    method = (body.get("method") or "POST").upper()
    if not name or not url:
        return jsonify({"error": "name and url required"}), 400

    engine_doc = {
        "_id": name,
        "name": name,
        "url": url,
        "method": method,
        "type": body.get("type", "instagram_mobile"),
        "active": bool(body.get("active", True)),
        "metadata": body.get("metadata", {})
    }
    engines_col.replace_one({"_id": name}, engine_doc, upsert=True)
    return jsonify({"ok": True, "engine": engine_doc})

@app.route("/engines", methods=["GET"])
@require_admin
def list_engines():
    engines = []
    for e in engines_col.find({}):
        _ = e.copy()
        _.pop("_id", None)
        engines.append(e)
    return jsonify({"ok": True, "engines": engines})

@app.route("/engines/<string:name>", methods=["DELETE"])
@require_admin
def delete_engine(name):
    res = engines_col.delete_one({"_id": name})
    return jsonify({"ok": True, "deleted_count": res.deleted_count})

# -------------------------
# Core endpoint: send reset
# -------------------------
@app.route("/reset", methods=["GET", "POST"])
def send_reset():
    global _last_global_reset_ts
    now = time.time()
    if now - _last_global_reset_ts < GLOBAL_COOLDOWN:
        remaining = round(GLOBAL_COOLDOWN - (now - _last_global_reset_ts), 2)
        return jsonify({"ok": False, "error": f"global cooldown: wait {remaining}s"}), 429

    if request.method == "POST":
        payload = request.get_json(force=True, silent=True) or {}
    else:  # GET request
        payload = {
            "engine": request.args.get("engine"),
            "target": request.args.get("target"),
            "requester_id": request.args.get("requester_id"),
            "requester_name": request.args.get("requester_name")
        }

    target = (payload.get("target") or "").strip()
    if not target:
        return jsonify({"ok": False, "error": "missing target (username or email)"})


    engine_name = payload.get("engine") or "instagram_mobile"
    engine_doc = engines_col.find_one({"_id": engine_name, "active": True})
    if not engine_doc:
        return jsonify({"ok": False, "error": f"engine '{engine_name}' not found or inactive"}), 404

    # Simple per-requester bookkeeping:
    requester_id = payload.get("requester_id") or f"api_user:{request.remote_addr}"
    requester_name = payload.get("requester_name") or requester_id

    # Build request (imitating your bot logic)
    _csrftoken, guid, device_id, user_agent = gen_random_values()
    headers = {"User-Agent": user_agent}
    data = {"_csrftoken": _csrftoken, "guid": guid, "device_id": device_id}

    # engine types: default behavior mirror of original script:
    if engine_doc.get("type") == "instagram_mobile":
        # choose correct field name
        if "@" in target:
            data["user_email"] = target
        else:
            data["username"] = target
    else:
        # fallback: if engine metadata has "field_for_target", use it
        field = engine_doc.get("metadata", {}).get("field_for_target") or "username"
        data[field] = target

    # (Optional) merge headers/data templates from engine metadata:
    metadata = engine_doc.get("metadata", {})
    for k, v in metadata.get("force_headers", {}).items():
        headers[k] = v
    for k, v in metadata.get("force_data", {}).items():
        data[k] = v

    # Send the HTTP request (synchronous)
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as client:
            if engine_doc.get("method", "POST").upper() == "POST":
                resp = client.post(engine_doc["url"], headers=headers, data=data)
            else:
                resp = client.get(engine_doc["url"], headers=headers, params=data)
            # attempt to parse json, but safe if not json
            try:
                resp_json = resp.json()
            except Exception:
                resp_json = {"raw_text": resp.text}

        _last_global_reset_ts = time.time()  # set global cooldown after sending

        # Interpret response similarly to the bot:
        status = resp_json.get("status") if isinstance(resp_json, dict) else None
        obf = resp_json.get("obfuscated_email") if isinstance(resp_json, dict) and resp_json.get("obfuscated_email") else obfuscate_account(target)

        result = {
            "ok": True,
            "engine": engine_doc["name"],
            "status_field": status or resp.status_code,
            "obfuscated_account": obf,
            "http_status": resp.status_code,
            "response": resp_json
        }

        # If engine reports success with status == "ok", update counters
        if (isinstance(resp_json, dict) and resp_json.get("status") == "ok") or resp.status_code in (200, 201):
            increment_stat("reset_counter", 1)
            add_leaderboard_entry(requester_id, requester_name, 1)
        # store requester (simple)
        users_col.update_one({"_id": requester_id}, {"$set": {"name": requester_name, "last_request": time.time()}}, upsert=True)

        return jsonify(result)

    except httpx.RequestError as e:
        return jsonify({"ok": False, "error": "http_request_error", "detail": str(e)}), 502
    except Exception as e:
        return jsonify({"ok": False, "error": "unexpected_error", "detail": str(e)}), 500

# -------------------------
# Simple admin stats
# -------------------------
@app.route("/stats", methods=["GET"])
@require_admin
def get_stats():
    total_users = users_col.count_documents({})
    reset_doc = stats_col.find_one({"_id": "reset_counter"})
    reset_count = reset_doc["count"] if reset_doc else 0
    top = list(leaderboard_col.find().sort([("count", -1), ("last_reset", -1)]).limit(10))
    top_list = [{"id": t["_id"], "name": t.get("name"), "count": t.get("count", 0)} for t in top]
    return jsonify({
        "ok": True,
        "total_tracked_requesters": total_users,
        "reset_count_total": reset_count,
        "top_requesters": top_list
    })

# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    # Create a default Instagram engine if not present (helpful for quick local testing)
    if not engines_col.find_one({"_id": "instagram_mobile"}):
        engines_col.replace_one({"_id": "instagram_mobile"}, {
            "_id": "instagram_mobile",
            "name": "instagram_mobile",
            "url": "https://i.instagram.com/api/v1/accounts/send_password_reset/",
            "method": "POST",
            "type": "instagram_mobile",
            "active": True,
            "metadata": {}
        }, upsert=True)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

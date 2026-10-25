#!/usr/bin/env python3
"""claude-status-watch: watch status.claude.com and notify you of incidents.

Standard library only (Python 3.9+). Subcommands:

  check        read the status page, notify on new incident / update / resolution,
               write the optional status file (default command)
  guard        exit 75 if a model is affected according to the status file (job launcher guard)
  notify-test  send a test message to every configured channel

Documentation: README.md and docs/ in the repository.
"""
import argparse
import json
import os
import re
import shlex
import smtplib
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.message import EmailMessage

VERSION = "1.0.0"
EXIT_PAUSED = 75
DEFAULT_URL = "https://status.claude.com/api/v2/summary.json"
IMPACT_RANK = {"none": 0, "maintenance": 0, "minor": 1, "major": 2, "critical": 3}

DEFAULTS = {
    "language": "en",
    "source_url": DEFAULT_URL,
    "state_file": "~/.claude-status-watch/state.json",
    "status_file": None,
    "message_prefix": "",
    "models": ["opus", "sonnet", "haiku", "fable"],
    "filters": {"components": [], "models": []},
    "notify_on": ["new", "update", "resolved", "component"],
    "all_models_components": ["Claude API", "Claude Code"],
    "all_models_min_impact": "major",
    "all_models_phrases": ["all models", "all claude models", "every model"],
    "channels": [],
}

TEXTS = {
    "en": {
        "new": "New incident", "update": "Incident update", "resolved": "Incident resolved",
        "component": "Component status change", "component_ok": "Component back to normal",
        "impact": "Impact", "status": "Status", "components": "Components", "models": "Models",
        "duration": "Duration", "none": "none named", "all": "all models",
        "details": "Details", "test": "Test message: this channel works.",
    },
    "fr": {
        "new": "Nouvel incident", "update": "Mise à jour d'incident", "resolved": "Incident résolu",
        "component": "Changement d'état d'un composant", "component_ok": "Composant revenu à la normale",
        "impact": "Impact", "status": "Statut", "components": "Composants", "models": "Modèles",
        "duration": "Durée", "none": "aucun cité", "all": "tous les modèles",
        "details": "Détails", "test": "Message de test : ce canal fonctionne.",
    },
}


def log(msg):
    print(f"{datetime.now().isoformat(timespec='seconds')} {msg}", flush=True)


# ---------------------------------------------------------------- configuration

def load_config(path):
    cfg = json.loads(json.dumps(DEFAULTS))
    if path:
        with open(os.path.expanduser(path), encoding="utf-8") as f:
            user = json.load(f)
        for key, val in user.items():
            if key.startswith("_"):
                continue
            if key == "filters" and isinstance(val, dict):
                cfg["filters"].update(val)
            else:
                cfg[key] = val
    cfg["models"] = [m.lower() for m in cfg["models"]]
    cfg["all_models_phrases"] = [m.lower() for m in cfg["all_models_phrases"]]
    cfg["filters"]["models"] = [m.lower() for m in cfg["filters"].get("models", [])]
    if cfg["language"] not in TEXTS:
        raise ValueError(f"unsupported language: {cfg['language']}")
    return cfg


def read_env_file(path):
    values = {}
    try:
        with open(os.path.expanduser(path), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                if key.startswith("export "):
                    key = key[7:].strip()
                values[key] = val.strip().strip("'\"")
    except OSError:
        pass
    return values


def secret(channel, key, default=None):
    """Value of `key` for a channel: `<key>_env` (variable name, then env_file), else literal `key`."""
    name = channel.get(key + "_env")
    if name:
        if os.environ.get(name):
            return os.environ[name]
        if channel.get("env_file"):
            val = read_env_file(channel["env_file"]).get(name)
            if val:
                return val
        return default
    return channel.get(key, default)


# ---------------------------------------------------------------- fetching

def fetch_json(source, timeout=20):
    if source.startswith(("http://", "https://")):
        req = urllib.request.Request(source, headers={"User-Agent": f"claude-status-watch/{VERSION}"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    path = source[7:] if source.startswith("file://") else source
    with open(os.path.expanduser(path), encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- analysis

def models_in(text, models):
    found = []
    low = text.lower()
    for m in models:
        if re.search(r"\b" + re.escape(m.lower()) + r"\b", low) and m.lower() not in found:
            found.append(m.lower())
    return found


def analyse_incident(inc, cfg, base_url):
    updates = inc.get("incident_updates") or []
    components = [c["name"] for c in inc.get("components") or []]
    for up in updates:
        for c in up.get("affected_components") or []:
            if c["name"] not in components:
                components.append(c["name"])
    title = inc.get("name", "")
    named = models_in(title, cfg["models"])
    bodies = " ".join(u.get("body", "") for u in updates)
    if not named:
        named = models_in(bodies, cfg["models"])
    low = (title + " " + bodies).lower()
    says_all = any(p in low for p in cfg["all_models_phrases"])
    impact = inc.get("impact", "none")
    hits_core = any(k.lower() in c.lower() for c in components for k in cfg["all_models_components"])
    all_affected = bool(says_all or (
        not named and hits_core and IMPACT_RANK.get(impact, 0) >= IMPACT_RANK[cfg["all_models_min_impact"]]))
    latest = updates[0] if updates else {}
    return {
        "id": inc["id"],
        "title": title,
        "status": inc.get("status", ""),
        "impact": impact,
        "components": components,
        "models": named,
        "all_models": all_affected,
        "started_at": inc.get("started_at") or inc.get("created_at") or "",
        "url": base_url + "/incidents/" + inc["id"],
        "last_update": latest.get("body", ""),
    }


def passes_filters(info, cfg):
    comp_f = [c.lower() for c in cfg["filters"].get("components", [])]
    mod_f = [m.lower() for m in cfg["filters"].get("models", [])]
    if comp_f and not any(f in c.lower() for f in comp_f for c in info["components"]):
        return False
    if mod_f and info["models"] and not info["all_models"] and not (set(mod_f) & set(info["models"])):
        return False
    return True


def build_status(incidents, summary, now_iso):
    models = {}
    for inc in incidents:
        for m in inc["models"]:
            entry = models.setdefault(m, {"since": inc["started_at"], "incidents": []})
            if inc["started_at"] and (not entry["since"] or inc["started_at"] < entry["since"]):
                entry["since"] = inc["started_at"]
            entry["incidents"].append(inc["id"])
    all_inc = [i for i in incidents if i["all_models"]]
    return {
        "schema": 1,
        "checked_at": now_iso,
        "ok": not incidents,
        "indicator": (summary.get("status") or {}).get("indicator", ""),
        "all_models_affected": bool(all_inc),
        "all_models_since": min((i["started_at"] for i in all_inc if i["started_at"]), default=None),
        "models_affected": models,
        "incidents": incidents,
    }


# ---------------------------------------------------------------- messages

def format_message(kind, info, cfg, extra=None):
    t = TEXTS[cfg["language"]]
    extra = extra or {}
    models = t["all"] if info.get("all_models") else (
        ", ".join(m.capitalize() for m in info.get("models", [])) or t["none"])
    title = f"{cfg['message_prefix']}{t[kind]}: {info['title']}"
    lines = []
    if info.get("impact") and kind in ("new", "update"):
        lines.append(f"{t['impact']}: {info['impact']}")
    if info.get("status"):
        lines.append(f"{t['status']}: {info['status']}")
    if info.get("components"):
        lines.append(f"{t['components']}: {', '.join(info['components'])}")
    if kind in ("new", "update", "resolved"):
        lines.append(f"{t['models']}: {models}")
    if extra.get("duration"):
        lines.append(f"{t['duration']}: {extra['duration']}")
    body = extra.get("body") or (info.get("last_update") if kind in ("new", "update") else "")
    if body:
        lines.append(f"{t['details']}: {body}")
    if info.get("url"):
        lines.append(info["url"])
    return title, "\n".join(lines)


def parse_ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def human_duration(start_iso, end_iso):
    try:
        mins = int((parse_ts(end_iso) - parse_ts(start_iso)).total_seconds() // 60)
    except (ValueError, TypeError, AttributeError):
        return ""
    return f"{mins // 60} h {mins % 60:02d} min" if mins >= 60 else f"{mins} min"


# ---------------------------------------------------------------- channels

def http_post(url, data, headers, timeout=20):
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        resp.read()


def send_telegram(ch, title, body):
    token, chat = secret(ch, "token"), secret(ch, "chat")
    if not token or not chat:
        raise ValueError("telegram token or chat id missing")
    payload = {"chat_id": chat, "text": f"{title}\n{body}".strip(), "disable_web_page_preview": True}
    thread = secret(ch, "thread")
    if thread and str(thread) not in ("0", ""):
        payload["message_thread_id"] = int(thread)
    base = ch.get("api_base", "https://api.telegram.org")
    http_post(f"{base}/bot{token}/sendMessage", json.dumps(payload).encode(),
              {"Content-Type": "application/json"})


def send_ntfy(ch, title, body):
    server = ch.get("server", "https://ntfy.sh").rstrip("/")
    headers = {"Title": title.encode("ascii", "replace").decode()}  # HTTP headers are latin-1 at best
    tok = secret(ch, "token")
    if tok:
        headers["Authorization"] = "Bearer " + tok
    if ch.get("priority"):
        headers["Priority"] = str(ch["priority"])
    http_post(f"{server}/{ch['topic']}", body.encode("utf-8"), headers)


def send_webhook_json(ch, key, title, body):
    url = secret(ch, "webhook")
    if not url:
        raise ValueError("webhook url missing")
    text = f"**{title}**\n{body}" if key == "content" else f"*{title}*\n{body}"
    http_post(url, json.dumps({key: text, **({"allowed_mentions": {"parse": []}} if key == "content" else {})}).encode(), {"Content-Type": "application/json"})


def send_email(ch, title, body):
    msg = EmailMessage()
    msg["Subject"], msg["From"] = title, ch["from"]
    msg["To"] = ", ".join(ch["to"]) if isinstance(ch["to"], list) else ch["to"]
    msg.set_content(body)
    security = ch.get("security", "starttls")
    if security not in ("starttls", "ssl", "none"):
        raise ValueError("email security must be starttls, ssl or none")
    port = int(ch.get("port", 465 if security == "ssl" else 587))
    cls = smtplib.SMTP_SSL if security == "ssl" else smtplib.SMTP
    with cls(ch["host"], port, timeout=30) as smtp:
        if security == "starttls":
            smtp.starttls()
        user, pwd = secret(ch, "user"), secret(ch, "password")
        if user and pwd:
            if security == "none":
                raise ValueError("refusing to send a password without encryption")
            smtp.login(user, pwd)
        smtp.send_message(msg)


def send_desktop(ch, title, body):
    env = dict(os.environ, CSW_TITLE=title, CSW_BODY=body)
    if sys.platform.startswith("linux"):
        cmd = ["notify-send", "--", title, body]
    elif sys.platform == "darwin":
        cmd = ["osascript", "-e",
               'display notification (system attribute "CSW_BODY") with title (system attribute "CSW_TITLE")']
    elif sys.platform == "win32":
        ps = ("Add-Type -AssemblyName System.Windows.Forms;Add-Type -AssemblyName System.Drawing;"
              "$n=New-Object System.Windows.Forms.NotifyIcon;$n.Icon=[System.Drawing.SystemIcons]::Information;"
              "$n.Visible=$true;$n.ShowBalloonTip(10000,$env:CSW_TITLE,$env:CSW_BODY,'Info');Start-Sleep 11;$n.Dispose()")
        cmd = ["powershell", "-NoProfile", "-Command", ps]
    else:
        raise ValueError("desktop notifications unsupported on this platform")
    subprocess.run(cmd, env=env, check=True, timeout=30)


def send_command(ch, title, body, event="", url=""):
    argv = ch["argv"] if isinstance(ch["argv"], list) else shlex.split(ch["argv"])
    env = dict(os.environ, CSW_TITLE=title, CSW_BODY=body, CSW_EVENT=event, CSW_URL=url)
    subprocess.run(argv, input=f"{title}\n{body}\n".encode(), env=env, check=True, timeout=30)


def notify(cfg, kind, title, body, url="", dry_run=False):
    """Send to every channel. True if at least one delivery succeeded (or dry run / no channel)."""
    if dry_run or not cfg["channels"]:
        print(f"[notify:{kind}] {title}\n{body}\n", flush=True)
        return True
    ok = False
    for ch in cfg["channels"]:
        ctype = ch.get("type", "")
        try:
            if ctype == "telegram":
                send_telegram(ch, title, body)
            elif ctype == "ntfy":
                send_ntfy(ch, title, body)
            elif ctype == "discord":
                send_webhook_json(ch, "content", title, body)
            elif ctype == "slack":
                send_webhook_json(ch, "text", title, body)
            elif ctype == "email":
                send_email(ch, title, body)
            elif ctype == "desktop":
                send_desktop(ch, title, body)
            elif ctype == "command":
                send_command(ch, title, body, kind, url)
            else:
                raise ValueError(f"unknown channel type {ctype!r}")
            ok = True
        except urllib.error.HTTPError as e:  # never log the URL: it can contain a token
            log(f"channel {ctype}: HTTP error {e.code}")
        except Exception as e:  # noqa: BLE001
            log(f"channel {ctype}: failed ({type(e).__name__})")
    return ok


# ---------------------------------------------------------------- state files

def write_json_atomic(path, data):
    path = os.path.expanduser(path)
    folder = os.path.dirname(path) or "."
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".csw-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def read_json(path, default):
    try:
        with open(os.path.expanduser(path), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def acquire_lock(state_path):
    """Lock object, or False if another run holds it. None where fcntl is missing (Windows)."""
    try:
        import fcntl
    except ImportError:
        return None
    lock = open(state_path + ".lock", "a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock.close()
        return False
    return lock


# ---------------------------------------------------------------- check

def cmd_check(args):
    cfg = load_config(args.config)
    state_path = os.path.expanduser(cfg["state_file"])
    os.makedirs(os.path.dirname(state_path) or ".", exist_ok=True)
    lock = acquire_lock(state_path)
    if lock is False:
        log("another run is in progress, skipping")
        return 0
    try:
        return run_check(args, cfg, state_path)
    finally:
        if lock:
            lock.close()


def run_check(args, cfg, state_path):
    source = args.summary_file or cfg["source_url"]
    try:
        summary = fetch_json(source)
    except Exception as e:  # noqa: BLE001
        log(f"fetch failed ({type(e).__name__}); state unchanged")
        return 1
    if not isinstance(summary, dict) or not isinstance(summary.get("incidents"), list) \
            or not isinstance(summary.get("components"), list):
        log("unexpected status format; state unchanged")
        return 1
    page_url = (summary.get("page") or {}).get("url") or "https://status.claude.com"
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    incidents = [analyse_incident(i, cfg, page_url) for i in summary.get("incidents", [])
                 if i.get("status") not in ("resolved", "postmortem")]
    state = read_json(state_path, {})
    known, uncovered_old = state.get("incidents", {}), state.get("uncovered", {})
    new_known, kinds = {}, cfg["notify_on"]

    for info in incidents:
        old = known.get(info["id"])
        signature = [info["status"], info["impact"], info["models"], info["all_models"]]
        kind = "new" if old is None else ("update" if old["signature"] != signature else None)
        record = dict(info, signature=signature, first_seen=(old or {}).get("first_seen", now_iso))
        if kind and kind in kinds and passes_filters(info, cfg):
            title, body = format_message(kind, info, cfg)
            if notify(cfg, kind, title, body, info["url"], args.dry_run):
                log(f"{kind}: {info['id']} {info['title']}")
            elif old is not None:
                record["signature"] = old["signature"]  # not delivered: retried next run
            else:
                continue  # new and not delivered: stays unknown, retried next run
        new_known[info["id"]] = record

    open_ids = {i["id"] for i in incidents}
    for iid, old in known.items():
        if iid in open_ids:
            continue
        extra = {"body": "", "duration": ""}
        if source.startswith("http"):
            try:
                detail = fetch_json(f"{page_url}/api/v2/incidents/{iid}.json")["incident"]
                ups = detail.get("incident_updates") or []
                extra["body"] = ups[0].get("body", "") if ups else ""
                extra["duration"] = human_duration(detail.get("started_at"), detail.get("resolved_at"))
            except Exception:  # noqa: BLE001
                pass
        if not extra["duration"]:
            extra["duration"] = human_duration(old.get("started_at") or old.get("first_seen"), now_iso)
        sent = True
        if "resolved" in kinds and passes_filters(old, cfg):
            title, body = format_message("resolved", dict(old, status="resolved"), cfg, extra)
            sent = notify(cfg, "resolved", title, body, old.get("url", ""), args.dry_run)
        if sent:
            log(f"resolved: {iid} {old['title']}")
        else:
            new_known[iid] = old  # kept until the end message is delivered

    covered = {c for i in incidents for c in i["components"]}
    uncovered_now = {c["name"]: c["status"] for c in summary.get("components", [])
                     if c.get("status") not in ("operational", None) and not c.get("group")
                     and c["name"] not in covered}
    if "component" in kinds:
        for name, st in list(uncovered_now.items()):
            if uncovered_old.get(name) != st:
                info = {"title": name, "status": st, "components": [name], "url": page_url}
                title, body = format_message("component", info, cfg)
                if not passes_filters(dict(info, models=[], all_models=False), cfg):
                    pass
                elif notify(cfg, "component", title, body, page_url, args.dry_run):
                    log(f"component: {name} {st}")
                elif name in uncovered_old:
                    uncovered_now[name] = uncovered_old[name]
                else:
                    del uncovered_now[name]
        current = {c["name"]: c.get("status") for c in summary["components"]}
        for name in uncovered_old:
            if name not in uncovered_now:
                if current.get(name) != "operational":
                    continue  # now covered by an open incident: no "back to normal" message
                info = {"title": name, "status": "operational", "components": [name], "url": page_url}
                title, body = format_message("component_ok", info, cfg)
                if not passes_filters(dict(info, models=[], all_models=False), cfg):
                    continue
                if not notify(cfg, "component", title, body, page_url, args.dry_run):
                    uncovered_now[name] = uncovered_old[name]

    if not args.dry_run:
        write_json_atomic(state_path, {"incidents": new_known, "uncovered": uncovered_now})
    if cfg.get("status_file"):
        status = build_status(incidents, summary, now_iso)
        if args.dry_run:
            print(json.dumps(status, indent=2, ensure_ascii=False))
        else:
            write_json_atomic(cfg["status_file"], status)
    return 0


# ---------------------------------------------------------------- guard

def cmd_guard(args):
    """Exit 0 = go, 75 = pause. Unknown or stale status = go, unless --fail-closed."""
    families = load_config(args.config)["models"] if args.config else DEFAULTS["models"]
    status = read_json(args.status_file, None)
    unknown = status is None
    if not unknown:
        try:
            age_min = (datetime.now(timezone.utc) - parse_ts(status["checked_at"])).total_seconds() / 60
            unknown = age_min > args.max_age
        except (KeyError, ValueError):
            unknown = True
    if unknown:
        print("status unknown or stale")
        return EXIT_PAUSED if args.fail_closed else 0
    if status.get("all_models_affected"):
        print(f"pause: all models affected since {status.get('all_models_since')}")
        return EXIT_PAUSED
    affected = status.get("models_affected", {})
    fam = next((f for f in families if f in (args.model or "").lower()), None)
    if fam:
        names = [fam] if fam in affected else []
    else:  # no model given or not recognised: any affected model pauses
        names = sorted(affected)
    if names:
        print("pause: " + ", ".join(f"{n} since {affected[n]['since']}" for n in names))
        return EXIT_PAUSED
    print("go")
    return 0


# ---------------------------------------------------------------- notify-test

def cmd_notify_test(args):
    cfg = load_config(args.config)
    title = f"{cfg['message_prefix']}claude-status-watch {VERSION}"
    return 0 if notify(cfg, "test", title, TEXTS[cfg["language"]]["test"], dry_run=args.dry_run) else 1


def build_parser():
    p = argparse.ArgumentParser(prog="claude_status_watch", description=__doc__.split("\n\n")[0])
    p.add_argument("--version", action="version", version=VERSION)
    sub = p.add_subparsers(dest="cmd")
    default_cfg = os.environ.get("CSW_CONFIG", "~/.claude-status-watch/config.json")
    for name in ("check", "notify-test", "guard"):
        sp = sub.add_parser(name)
        if name == "guard":
            sp.add_argument("--config", help="optional: reads the model families from it")
            sp.add_argument("--status-file", required=True)
            sp.add_argument("--model", help="model id or family (opus, sonnet, haiku, fable); omit = any model")
            sp.add_argument("--max-age", type=float, default=30.0, help="minutes before the status file is stale")
            sp.add_argument("--fail-closed", action="store_true", help="pause when the status is unknown or stale")
            continue
        sp.add_argument("--config", default=default_cfg)
        sp.add_argument("--dry-run", action="store_true", help="print messages, send nothing, write no state")
        if name == "check":
            sp.add_argument("--summary-file", help="read this local JSON instead of the status page (tests)")
    return p


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0].startswith("-") and argv[0] not in ("-h", "--help", "--version"):
        argv = ["check"] + argv
    args = build_parser().parse_args(argv)
    try:
        return {"check": cmd_check, "guard": cmd_guard, "notify-test": cmd_notify_test}[args.cmd](args)
    except (OSError, ValueError, KeyError) as e:
        log(f"error: {type(e).__name__}: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())

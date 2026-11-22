"""Resident llama-server for the active profile (profiles.py): started once, kept loaded while idle, restarted if it dies, swapped on switch()."""
import atexit
import base64
import ctypes
import json
import os
import signal
import subprocess
import threading
import time
import urllib.request

from . import profiles

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(HERE, "third_party", "llama.cpp", "build", "bin", "llama-server")
MANIFEST = os.path.join(HERE, "models", "manifest.json")
PORT = 8089
URL = f"http://127.0.0.1:{PORT}"
# serving settings (spec section 6): one model, one slot, small context, deterministic
CTX = 4096
MAX_NEW_TOKENS = 256

PROFILE_FILE = os.path.join(HERE, "profile.json")
STATE = dict(name="", profile="", label="", state="not started", loaded=False, busy=False, analyzed=0, last_s=0.0, error="",
             restarts=0, vram_mib=None, queued=0, switching=False, loaded_s=None)
_ACTIVE = profiles.DEFAULT
_hold = False                        # True while switch() swaps the model: the supervisor must not touch the process
_READY = threading.Condition()
GPU_LOCK = threading.Lock()          # exactly one request on the GPU at a time
_proc = None
_stop = False


def _load_active():
    global _ACTIVE
    try:
        n = json.load(open(PROFILE_FILE)).get("profile")
        if n in profiles.PROFILES:
            _ACTIVE = n
    except (OSError, ValueError):
        pass
    _set_names()


def _set_names():
    p = profiles.PROFILES[_ACTIVE]
    STATE.update(name=p["model_name"], profile=_ACTIVE, label=p["label"])


def profile():
    """The active profile dict (with its id)."""
    return dict(profiles.PROFILES[_ACTIVE], id=_ACTIVE)


def installed(pid):
    try:
        m = json.load(open(MANIFEST))
    except (OSError, ValueError):
        return False
    k = profiles.PROFILES[pid]["manifest_key"]
    files = m["files"] if k is None else m.get(k, {}).get("files")
    return bool(files) and all(os.path.exists(f["path"]) for f in files.values())


def available():
    return os.path.exists(BIN) and os.path.exists(MANIFEST)


def _paths():
    m = json.load(open(MANIFEST))
    k = profiles.PROFILES[_ACTIVE]["manifest_key"]
    fs = list((m["files"] if k is None else m[k]["files"]).values())
    fs = [f for f in fs if f["path"].endswith(".gguf")]
    model = next(f["path"] for f in fs if not os.path.basename(f["path"]).startswith("mmproj"))
    proj = next(f["path"] for f in fs if os.path.basename(f["path"]).startswith("mmproj"))
    return model, proj


PIDFILE = os.path.join(HERE, "logs", "llama-server.pid")


def _kill_stale():
    """A llama-server left behind by an earlier dashboard run would hold the port (and must not be reused: unknown settings)."""
    try:
        pid = int(open(PIDFILE).read())
        if "llama-server" in open(f"/proc/{pid}/cmdline").read():
            os.kill(pid, signal.SIGTERM)
            for _ in range(50):
                if not os.path.exists(f"/proc/{pid}"):
                    break
                time.sleep(0.1)
    except (OSError, ValueError):
        pass


def _die_with_parent():
    ctypes.CDLL("libc.so.6").prctl(1, signal.SIGTERM)    # PR_SET_PDEATHSIG: the child dies when the dashboard dies


def _spawn():
    global _proc
    _kill_stale()
    model, proj = _paths()
    log = open(os.path.join(HERE, "logs", "llama-server.log"), "ab")
    cmd = [BIN, "-m", model, "--mmproj", proj, "-ngl", "99", "-c", str(CTX), "--parallel", "1", "--host", "127.0.0.1", "--port", str(PORT),
           "--temp", "0", "-n", str(MAX_NEW_TOKENS), "--no-webui", "--cache-ram", "0"] + profiles.PROFILES[_ACTIVE]["llama_args"]
    STATE["_t_spawn"] = time.time()
    _proc = subprocess.Popen(cmd, stdout=log, stderr=log, preexec_fn=_die_with_parent)
    open(PIDFILE, "w").write(str(_proc.pid))
    STATE.update(state="loading model", loaded=False)


def healthy():
    try:
        with urllib.request.urlopen(URL + "/health", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def chat(messages, max_tokens=MAX_NEW_TOKENS, timeout=180):
    """One stateless chat completion. messages: OpenAI-style list (images as data: URLs)."""
    body = json.dumps(dict(messages=messages, max_tokens=max_tokens, temperature=0, stream=False, cache_prompt=False)).encode()
    req = urllib.request.Request(URL + "/v1/chat/completions", data=body, headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.loads(r.read())
    return out["choices"][0]["message"]["content"].strip(), out.get("usage", {})


def _warm():
    import cv2
    import numpy as np
    img = np.full((224, 224, 3), 127, np.uint8)
    ok, jpg = cv2.imencode(".jpg", img)
    url = "data:image/jpeg;base64," + base64.b64encode(jpg.tobytes()).decode()
    chat([{"role": "user", "content": [{"type": "text", "text": "Describe this image in one short sentence."},
                                       {"type": "image_url", "image_url": {"url": url}}]}], max_tokens=16)


def _supervisor():
    global _stop
    fails = 0
    while not _stop:
        if _hold:
            time.sleep(0.3)
            continue
        if _proc is None or _proc.poll() is not None:
            if _proc is not None:
                STATE["restarts"] += 1
                STATE.update(state="crashed, restarting", loaded=False)
                fails += 1
                if fails > 3:
                    STATE.update(state="failed (see vlm_agent/logs/llama-server.log)", error="llama-server keeps exiting")
                    return
            try:
                _spawn()
            except Exception as e:
                STATE.update(state="failed", error=repr(e)); return
        if not STATE["loaded"] and _proc is not None and _proc.poll() is None and healthy():
            try:
                _warm()
                STATE.update(state="idle (model resident, waiting for a chunk)", loaded=True, error="", switching=False,
                             loaded_s=round(time.time() - STATE.get("_t_spawn", time.time()), 1))
                with _READY:
                    _READY.notify_all()
                fails = 0
            except Exception as e:
                STATE["error"] = "warm-up: " + repr(e)
        time.sleep(1.0)


def start():
    """Start the supervisor thread (non-blocking). Returns False if the runtime/models are not installed."""
    if not available():
        STATE.update(state="not installed (run vlm_agent/setup.sh)")
        return False
    _load_active()
    if not installed(_ACTIVE):
        STATE.update(state="profile files missing (run vlm_agent/setup.sh / setup_lfm.sh)", error=_ACTIVE + " not installed")
        return False
    threading.Thread(target=_supervisor, daemon=True).start()
    return True


atexit.register(lambda: _proc and _proc.poll() is None and _proc.terminate())


def wait_ready(timeout=300):
    """Block until the resident model is loaded (e.g. during a profile switch). True when ready."""
    end = time.time() + timeout
    with _READY:
        while not STATE["loaded"] and time.time() < end and not _stop:
            _READY.wait(1.0)
    return STATE["loaded"]


def switch(new):
    """Swap the resident model. Runs in a thread: waits for the running analysis (GPU_LOCK), stops llama-server, the supervisor starts the new one."""
    global _ACTIVE, _proc, _hold
    if new not in profiles.PROFILES:
        return False, "unknown profile"
    if not installed(new):
        return False, "profile files not installed (run vlm_agent/setup_lfm.sh)" if new == "lfm3_omni_av" else "profile files not installed"
    if new == _ACTIVE and (STATE["loaded"] or STATE["switching"]):
        return True, "already active"
    if STATE["switching"]:
        return False, "a switch is already in progress"

    def work():
        global _ACTIVE, _proc, _hold
        _hold = True
        STATE.update(switching=True, state="switching: waiting for the running analysis", loaded=False)
        with GPU_LOCK:
            STATE.update(state="switching: unloading " + STATE["name"])
            p = _proc
            _proc = None                          # the supervisor sees "no process" and starts the new profile
            if p is not None and p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    p.kill(); p.wait()
            _ACTIVE = new
            _set_names()
            json.dump(dict(profile=new), open(PROFILE_FILE, "w"))
            STATE.update(state="switching: loading " + STATE["name"], error="", restarts=0)
        _hold = False
    threading.Thread(target=work, daemon=True).start()
    return True, "switching"


def restart():
    """Kill the llama-server process now (an analysis in flight fails and its chunk is skipped), free the GPU memory and let the supervisor
    start it again, which reloads the weights and warms the model up."""
    global _proc, _hold
    if STATE["switching"]:
        return False, "a switch/restart is already in progress"

    def work():
        global _proc, _hold
        _hold = True
        STATE.update(switching=True, state="restarting: killing the GPU process", loaded=False)
        p = _proc
        _proc = None
        if p is not None and p.poll() is None:
            p.kill()
            try:
                p.wait(timeout=20)
            except subprocess.TimeoutExpired:
                pass
        _kill_stale()
        if GPU_LOCK.acquire(timeout=60):                # an analysis that was mid-request has failed by now and released the GPU
            GPU_LOCK.release()
        STATE.update(state="restarting: reloading weights", error="", restarts=0)
        _hold = False                                   # the supervisor spawns llama-server, loads the weights and warms up
    threading.Thread(target=work, daemon=True).start()
    return True, "restarting"


def stop():
    global _stop
    _stop = True
    if _proc and _proc.poll() is None:
        _proc.terminate()

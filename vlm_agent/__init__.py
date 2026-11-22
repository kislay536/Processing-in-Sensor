"""vlm_agent: self-contained local scene-report agent. Delete this folder to remove it; the dashboard keeps working without it.

Hooks used by the rest of the project (all guarded with try/except at the call sites):
  vlm_agent.start()            -> start the resident model server (non-blocking)
  vlm_agent.analyze(event_dir, meta, report)  -> analyzer-cascade entry, adds report['scene']
  vlm_agent.status()           -> dict for the dashboard GPU panel
"""
import json
import os

from . import agent, profiles, server


def start():
    return server.start()


def status():
    return dict(server.STATE)


def profiles_status():
    """For the dashboard: all profiles, which is active, and whether their files are installed."""
    return dict(active=server.STATE["profile"] or profiles.DEFAULT, state=server.STATE["state"], loaded=server.STATE["loaded"],
                switching=server.STATE["switching"], loaded_s=server.STATE["loaded_s"],
                profiles=[dict(id=k, label=v["label"], mode=v["mode"], model=v["model_name"], installed=server.installed(k), board=v["board"])
                          for k, v in profiles.PROFILES.items()])


def switch(profile_id):
    return server.switch(profile_id)


def restart():
    return server.restart()


def board_params():
    """Board parameters belonging to the active profile (e.g. trig_mode)."""
    return dict(profiles.PROFILES[server.STATE["profile"] or profiles.DEFAULT]["board"])


def analyze(event_dir, meta, report):
    st = server.STATE
    if not st["loaded"] and (st["switching"] or st["state"].startswith("loading")):
        server.wait_ready(300)           # a profile switch / model load in progress: chunks wait instead of being skipped
    if not st["loaded"]:
        report["sections"]["Scene report (VLM)"] = "skipped: model " + server.STATE.get("state", "not available")
        return
    import time
    t = time.time()
    rep = agent.analyze_chunk(event_dir, meta)
    server.STATE.update(analyzed=server.STATE["analyzed"] + 1, last_s=round(time.time() - t, 2))
    with open(os.path.join(event_dir, "scene.json"), "w") as fh:
        json.dump(rep, fh, indent=1)
    report["scene"] = rep
    report["sections"]["Scene report (%s)" % rep["model"].split("/")[-1]] = agent.to_markdown(rep)
    if rep["summary"]:
        report["summary"] = rep["summary"]

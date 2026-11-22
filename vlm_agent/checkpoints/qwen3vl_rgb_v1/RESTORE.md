# Checkpoint: Qwen3-VL-2B RGB scene agent (v1, 2026-11-22)
State when saved: resident llama-server (Qwen3VL-2B-Instruct Q4_K_M + mmproj Q8_0), RGB only, motion + scene-context chunks, 9/9 checks in
`vlm_agent/tests/check_agent.py` passed, live context chunks described in ~1 s, idle GPU 0 % after the orphan-server fix.
Contents: vlm_agent_code.tgz (all vlm_agent python/setup/README/tests, without models and llama.cpp build), manifest.json (model files + sha256),
snapshots of the project files that hook into it (ui_server.py, ui_index.html, analyzers_init.py, chunks.py, proto.py) and firmware backup
`board/sw/main_step3_ctx.c.bak`.
Restore the agent code:  tar xzf vlm_agent/checkpoints/qwen3vl_rgb_v1/vlm_agent_code.tgz   (from the project root; models stay in vlm_agent/models)
Restore a hook file:     cp vlm_agent/checkpoints/qwen3vl_rgb_v1/<name>.snapshot <original path>
After the profile switch exists, this setup is the profile "qwen3vl_rgb" (the default).

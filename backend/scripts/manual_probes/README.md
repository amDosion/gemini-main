# Manual probes (NOT collected by pytest)

These are real-network, credential-dependent probe scripts moved out of `backend/tests/` so pytest never collects them. Run them by hand from `backend/` with the venv (e.g. `python -m scripts.manual_probes.manual_probe_batch_image`); they hit live provider gateways using the local OpenAI profile and incur real cost. Never wire them into CI.

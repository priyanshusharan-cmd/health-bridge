# AMD inference setup and evidence

The app's configurable provider sends `/chat/completions` requests to an OpenAI-compatible model server. The `rocm` setting chooses this adapter; it does not inspect or certify remote hardware.

## Event runtime

Use the AMD Developer Cloud environment allocated for the event. Choose an image compatible with its GPU and ROCm version. The official vLLM documentation describes AMD images at https://docs.vllm.ai/en/latest/deployment/docker/ and supported GPUs at https://docs.vllm.ai/en/latest/getting_started/installation/gpu/ . Follow the current vendor installation instructions rather than installing an arbitrary ROCm image on this Mac.

Inside a supported ROCm/vLLM environment, a starting command is:

```sh
vllm serve Qwen/Qwen2.5-7B-Instruct --host 127.0.0.1 --port 8001 --max-model-len 8192
```

The model card lists Apache-2.0 licensing: https://huggingface.co/Qwen/Qwen2.5-7B-Instruct . Check the actual model revision, available GPU memory and language performance before final selection. This is a swappable baseline, not a claim that it is best for Kannada.

On the app host, use a private connection/SSH tunnel to that endpoint. Do not expose an unauthenticated model endpoint publicly. Set `AI_API_KEY` when endpoint authentication is configured.

```sh
AI_BACKEND=rocm \
AI_BASE_URL=http://127.0.0.1:8001/v1 \
AI_MODEL=Qwen/Qwen2.5-7B-Instruct \
.venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

## Prove execution, don't just label it

In the AMD environment:

```sh
python -c "import torch; print('HIP:',torch.version.hip); print('GPU available:',torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

Generate a brief from the frontend. Save the model server request logs, GPU identity and HIP version, model/version, timestamp, elapsed time displayed in the brief, and screenshots of the actual working journey. Include at least three runs and an honest CPU/source-only baseline; never invent acceleration numbers. The health endpoint intentionally reports `amd_verified=false` until actual evidence is collected and a proper verification mechanism is implemented.

## Cost control

Start GPU compute only for integration/measurement/demo sessions; stop it afterward. Event credits are finite, not free hosting forever. No training/fine-tuning is necessary. The app sends a maximum of 13 sources (one intake plus 12 records), at most 2400 characters each, and caps output at 2200 tokens. One retry is allowed for malformed/unverifiable output. Briefs are persisted, and generation happens only on user action.

## Current verification

The HTTP adapter and source validation have automated tests. An AMD model server has not been available in this development environment. Live AMD inference and quality/latency measurements remain mandatory before claiming a hackathon-ready AMD integration.

## Collect measured evidence

With the live endpoint configured in your environment:

```sh
.venv/bin/python scripts/benchmark_model.py --runs 3
```

This sends three bounded requests using synthetic records and saves `submission/model-evidence.json`. It does not log secrets or endpoint URLs. It refuses source-only mode. Attach matching GPU/server logs separately; the script does not pretend to attest to a remote GPU.

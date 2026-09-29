"""One request to check the HF token, the router and the model (a fraction of a cent).

    HF_TOKEN=... python inference/api_smoke.py
"""
import os, sys
from openai import OpenAI

token = os.environ.get("HF_TOKEN")
if not token:
    sys.exit("export HF_TOKEN=hf_... first (fine-grained, 'Make calls to Inference Providers')")
client = OpenAI(api_key=token,
                base_url=os.environ.get("API_BASE", "https://router.huggingface.co/v1"))
resp = client.chat.completions.create(
    model=os.environ.get("MODEL", "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B:nscale"),
    messages=[{"role": "user", "content": "What is 12 times 8? Answer briefly."}],
    max_tokens=256, temperature=0.6, timeout=120)
print("API_OUTPUT:", resp.choices[0].message.content)
print("usage:", resp.usage.prompt_tokens, "in /", resp.usage.completion_tokens, "out")
print("API_SMOKE_OK")

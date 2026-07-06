"""Kimi API 连通性测试脚本（同步版本）."""

import json
import os
import sys

import httpx


def test_model(model_id: str, api_key: str, think_mode: bool = True):
    print(f"\n{'='*60}", flush=True)
    print(f"Testing model: {model_id} (think_mode={think_mode})", flush=True)
    print(f"{'='*60}", flush=True)

    url = "https://api.moonshot.cn/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, reply with a short sentence."},
        ],
        "max_tokens": 256,
        "stream": False,
    }

    if model_id.lower().startswith("kimi-k2"):
        if "k2.7" in model_id.lower():
            payload["thinking"] = {"type": "enabled"}
        else:
            payload["thinking"] = {"type": "enabled" if think_mode else "disabled"}
    else:
        payload["temperature"] = 0.7

    print(f"Request URL: {url}", flush=True)
    print(f"Request body:\n{json.dumps(payload, ensure_ascii=False, indent=2)}", flush=True)

    try:
        with httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            response = client.post(url, headers=headers, json=payload)
            print(f"status: {response.status_code}", flush=True)
            print(f"body: {response.text[:2000]}", flush=True)

            if response.status_code == 200:
                data = response.json()
                message = data.get("choices", [{}])[0].get("message", {})
                content = message.get("content", "")
                reasoning = message.get("reasoning_content", "")
                print(f"\n[OK] content: {content[:200]}", flush=True)
                if reasoning:
                    print(f"[OK] reasoning: {reasoning[:200]}", flush=True)
            else:
                print(f"\n[ERROR] status {response.status_code}", flush=True)
    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}", flush=True)


def main():
    api_key = os.environ.get("MOONSHOT_API_KEY")
    if not api_key:
        print("Please set environment variable MOONSHOT_API_KEY", flush=True)
        print("PowerShell: $env:MOONSHOT_API_KEY='sk-xxx'", flush=True)
        print("cmd:        set MOONSHOT_API_KEY=sk-xxx", flush=True)
        sys.exit(1)

    test_model("kimi-k2.6", api_key, think_mode=True)
    test_model("kimi-k2.6", api_key, think_mode=False)
    test_model("kimi-k2.7-code", api_key, think_mode=True)


if __name__ == "__main__":
    main()

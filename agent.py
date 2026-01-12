import sys
import json
import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3"


def _build_prompt(pod_name: str, logs: str, runbook_chunks: list[str]) -> str:
    context_section = ""
    if runbook_chunks:
        joined = "\n\n---\n\n".join(runbook_chunks)
        context_section = f"""
## Relevant Runbook Context
{joined}

"""

    # Being explicit about output format up front reduces the chance the model
    # wraps the answer in conversational filler.
    return f"""You are an expert SRE assistant. Analyze the following crash logs and output ONLY two sections with no preamble:

**Root Cause:** <one or two sentences explaining why the pod crashed>
**Suggested Fix:** <concrete steps an engineer can take to resolve this>

Do not include any other text, greetings, or explanations outside those two sections.
{context_section}
## Crash Logs for pod `{pod_name}`
```
{logs[-3000:]}
```
"""


def query_llm(pod_name: str, logs: str, runbook_chunks: list[str]) -> str:
    prompt = _build_prompt(pod_name, logs, runbook_chunks)

    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,   # low temp = more deterministic, less hallucination
            "num_predict": 512,
        },
    }

    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=120)
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        print("\033[1;31mError:\033[0m Cannot reach Ollama at localhost:11434.")
        print("  Make sure Ollama is running: \033[1mollama serve\033[0m")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print("\033[1;31mError:\033[0m Ollama request timed out after 120s.")
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        if resp.status_code == 404:
            print(f"\033[1;31mError:\033[0m Model '{MODEL}' not found in Ollama.")
            print(f"  Pull it first: \033[1mollama pull {MODEL}\033[0m")
        else:
            print(f"\033[1;31mError:\033[0m Ollama returned HTTP {resp.status_code}: {e}")
        sys.exit(1)

    data = resp.json()
    return data.get("response", "").strip()

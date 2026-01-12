# kube-log-agent

A local Kubernetes debugging assistant that finds crashing pods, pulls their logs, and uses a local LLM to tell you what broke and how to fix it.

---

I built this because I got tired of the same loop: `kubectl get pods`, spot something in CrashLoopBackOff, `kubectl logs --previous`, grep through a wall of Go panic traces or Kafka connection timeouts, tab over to Confluence to search the runbooks, repeat. This tool does all of that in one command and gives you a plain-English answer in under 30 seconds — no cloud, no API keys, everything runs locally.

---

## Prerequisites

- Python 3.10+
- A configured `kubectl` context (`kubectl get pods` should work)
- [Ollama](https://ollama.com) running locally with `llama3` pulled:

```bash
ollama serve          # in a separate terminal, or run as a daemon
ollama pull llama3
```

## Quickstart

```bash
# Clone and set up
git clone https://github.com/you/kube-log-agent
cd kube-log-agent

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Drop your runbook .md files into the runbooks/ directory
# (a few example runbooks are included to get you started)

# Run it
python main.py debug
python main.py debug -n my-namespace   # scan a specific namespace
python main.py debug --all             # analyze every crashing pod, not just the worst one
```

On the first run it will embed and index your runbooks into a local ChromaDB. Subsequent runs skip re-indexing unless you pass `--reindex` or add new runbooks with `python main.py index`.

## Project Layout

```
kube-log-agent/
├── main.py         # CLI entrypoint and output formatting
├── k8s.py          # Kubernetes client: pod discovery and log fetching
├── vector_db.py    # ChromaDB indexing and semantic search over runbooks
├── agent.py        # Ollama prompt construction and LLM query
├── runbooks/       # Your .md runbooks (add as many as you want)
│   ├── crashloopbackoff.md
│   ├── oom-killed.md
│   └── database-connection-errors.md
└── requirements.txt
```

## Adding Your Own Runbooks

Drop any `.md` file into `runbooks/` and run `python main.py index`. The tool chunks by Markdown headers so you get better semantic matching if your runbooks are structured with `##` sections rather than one big blob of text.

## How It Works

1. Connects to your current kubeconfig context and lists pods in the target namespace.
2. Finds pods in `CrashLoopBackOff`, `Error`, `OOMKilled`, or with a high restart count.
3. Fetches the last 500 lines from the previous (crashed) container instance.
4. Does a semantic search over your runbooks to find the most relevant context.
5. Sends logs + runbook context to `llama3` via Ollama and asks for a root cause and fix.
6. Prints the result to your terminal.

No data leaves your machine.

## Limitations

- Only supports single-container pods for log fetching right now (multi-container support is a one-liner addition if you need it).
- LLM output quality depends on how good your runbooks are. Garbage in, garbage out.
- Tested against Kubernetes 1.28+.

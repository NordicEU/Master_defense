# Master Defense

This folder is self-contained for the defense demo and the thesis-based generated request flow.

## VM Setup

Install Python dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Install a local Ollama server on the VM:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Prepare Ollama and pull the model used by generated adversarial requests:

```bash
export OLLAMA_MODEL=llama3
./scripts/ensure_ollama.sh
```

The generator defaults to:

```bash
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=llama3
```

You can change those environment variables before running the app.

## Run

```bash
./start_all.sh
```

Open:

```text
http://127.0.0.1:8080
```

The input app supports manual submissions and generated request batches. The generated request path uses the local folder:

```text
thesis_generation_source/
```

That folder contains the trimmed thesis generation logic and XML source data needed at runtime.

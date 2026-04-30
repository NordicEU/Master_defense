# Master Defense

This folder is a self-contained defense demo for tax-submission handling. It combines a browser-facing input app, a gateway with layered analysis, multiple response services, an operator dashboard, and thesis-based generated request flows.

## What the project does

At a high level:

1. A submission enters through the input app.
2. The gateway runs the request through rule, anomaly, context, and semantic analysis.
3. The decision service turns the fused risk into a defense action.
4. The request is routed to one of several destinations:
   - `ALLOW` -> business app
   - `CONTAIN` -> quarantine service
   - `HONEYPOT` -> review service
   - `DECEIVE` -> deception service
   - `MINEFIELD` -> minefield service

The project is file-backed rather than database-backed. Runtime artifacts are written under `runtime/`.

## Main browser entry points

- Input app: `http://127.0.0.1:8080`
- Ops dashboard: `http://127.0.0.1:8090/ops`
- Business app: `http://127.0.0.1:8004`

## Main components

### Apps

- `apps/input_app`
  Manual submission form plus generated request batches.

- `apps/ops_app`
  Operator dashboard for containment, subject-control state, minefield cases, and accepted-request visibility.

- `apps/business_app`
  Small business-facing acceptance service and dashboard for allowed submissions.

### Services

- `services/gateway_service`
  Central routing point. Calls analysis services, fuses risk, calls the decision service, then forwards the request.

- `services/decision_service`
  Produces the final `DecisionResult` used for routing.

- `services/quarantine_service`
  Owns containment cases, subject control, audit trail, and transfer-to-minefield behavior.

- `services/defer_service`
  Current minefield service. Stores escalated cases and supports status progression, analyst notes, and resolution reasons.

- `services/deception_service`
  Deception-path placeholder service.

- `services/review_service`
  Honeypot/review-path service.

## Generated requests

The generated request flow uses `thesis_generation_source/`, which contains trimmed thesis generation logic and XML-backed source material.

Inside the input app, generated adversarial requests support two engines:

- `fallback`
  Fast local mutation of a green sample. No Ollama dependency.

- `llm`
  Uses the adversarial generator with Ollama to create more semantically plausible adversarial variants. Falls back to local mutation if model generation fails.

Relevant defaults:

```bash
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=llama3
```

## VM setup

Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Install Ollama on the VM:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Prepare Ollama and pull the configured model:

```bash
export OLLAMA_MODEL=llama3
./scripts/ensure_ollama.sh
```

If VM memory is tight, a smaller model such as `qwen2.5:3b` can be used instead:

```bash
export OLLAMA_MODEL=qwen2.5:3b
./scripts/ensure_ollama.sh
```

## Run locally on the VM

Start the full stack:

```bash
./start_all.sh
```

Stop the full stack:

```bash
./stop_all.sh
```

The startup script launches these ports:

- `8000` gateway
- `8001` intake
- `8002` decision
- `8003` quarantine
- `8004` business
- `8005` review
- `8006` minefield
- `8007` deception
- `8011` rule engine
- `8012` anomaly scorer
- `8013` context validator
- `8014` semantic assist
- `8080` input app
- `8090` ops app

## Minefield state

The minefield service now persists real case records under:

```text
runtime/defer_cases/
```

Each case currently supports:

- status progression:
  `queued`, `under_investigation`, `confirmed_hostile`, `released`
- analyst notes
- `resolution_reason`
- placeholders for future controls:
  `progressive_delay`, `behavior_capture`, `link_analysis`, `auto_blacklist`

These placeholders are there so the minefield path already has a structure for future cyber-defense behavior without needing another schema rewrite.

## Runtime data

Important runtime locations:

- `runtime/quarantine_cases/`
  Containment case files and subject-control records

- `runtime/defer_cases/`
  Minefield case files

- `runtime/metrics/accepted_submissions.jsonl`
  Accepted business submissions

- `runtime/audit_logs/`
  Audit logs and supporting artifacts

## Demo walkthrough

A simple demo flow for the defense presentation:

1. Start the stack with:

```bash
./start_all.sh
```

2. Open the input app:

```text
http://127.0.0.1:8080
```

3. Show a normal-looking manual or generated request that is accepted.
   Then open the business app:

```text
http://127.0.0.1:8004
```

   This shows the accepted-request counter and recent accepted submissions.
   Keep this page open during the demo as a live indicator of how many requests are actually making it through the defense layer into the business flow.

4. Submit a suspicious request that routes to containment.
   Then open the ops dashboard:

```text
http://127.0.0.1:8090/ops
```

   Show:
   - containment case count
   - restricted subject count
   - subject-control records

5. Open the containment views in ops:

```text
http://127.0.0.1:8090/ops/contain
http://127.0.0.1:8090/ops/subjects
```

   This shows how the suspicious subject is restricted while the case is under controlled handling.

6. Show an extreme or highly adversarial request that routes to minefield.
   Then open:

```text
http://127.0.0.1:8090/ops/minefield
```

   Use this to explain:
   - escalated cases
   - minefield status progression
   - analyst notes and resolution reason
   - future placeholders for progressive delay, behavior capture, link analysis, and auto-blacklist

7. If needed, explain the generated request modes.
   In the input app:
   - `green` generates normal-looking cases
   - `adversarial` generates suspicious cases
   - `mixed` blends both
   - `fallback` uses local mutation
   - `llm` uses Ollama-backed adversarial generation

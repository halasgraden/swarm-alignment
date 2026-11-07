# Swarm credit experiment

A small, turn-based testbed for studying whether visible individual credit, shared rewards, and audited rewards affect agents working on a shared board. This is a **research prototype**, not a security sandbox. Current implementation includes a deterministic mock policy to validate the environment. An Ollama adapter supports local language models; it has not yet been exercised against a live model on this machine.

## Quick start

Python 3.10+; standard library only. From this directory:

```sh
python3 -m unittest discover -s tests -v
python3 -m swarm_lab.run --config configs/example.json --seed 42 --output runs/demo
python3 -m swarm_lab.analyze runs/demo
```

The output directory must not already exist. Each execution writes `manifest.json`, private initial and final task snapshots with answer keys, `trajectory.jsonl` with every model observation, response, environment event, and a `metrics.json` summary. The manifest includes a SHA-256 checksum of the trajectory. Records are append-only during the run, but this is not tamper-proof storage; preserve output files externally if stronger integrity is needed. Do not give the private snapshots to an agent. The mock policy uses the public numbers to calculate answers; its outputs are **not experimental findings**.

## Controls

Copy and edit `configs/example.json`. Change `reward` to `team`, `individual`, or `audited`; use `task_count` for workload, `seeded_tasks` for initial contributions, `agents` and `actions_per_agent` for capacity, `starting_points` for a common score offset, and `elimination` for midpoint removal. Equal starting points are a score offset, not spendable resources; changing them alone does not affect rank-based elimination. The scheduler shuffles agents each round using a seeded PRNG. Task generation and elimination have separate seeded random streams. Identical seeds generate matched tasks across reward conditions when task count and seeded count are fixed.

All tasks require verification of their final version; each verify action checks the current answer. A new write increments the version, even when its text is unchanged. The audit counts a final version as verified if it was checked, irrespective of who checked it. The public verifier recomputes from the task record; the offline grader compares against the generated key. It is not a fully independent implementation because both ultimately rely on the same generated arithmetic inputs—cross-check generated keys before making claims.

Individual scoring gives the last author credit for each nonempty answer regardless of correctness. Shared scoring reflects final correct answers and thus reveals aggregate correctness to agents. Audited credit rewards correctness improvements and the first detection of a wrong answer version; the latter prevents repeated-check farming. These mechanisms differ in information exposed as well as incentives, so conclusions cannot isolate incentives alone. Compare behavior as well as outcomes and consider a matched-information control before causal claims.

## Metrics and limits

Metrics count correct, wrong and blank answers, cross-author answer transitions, unverified final answers, and overlap while at least one task has not been acted on. The overlap measure includes useful verification; inspect trajectories and do not call all overlap waste. A pre-seeded answer's author is `prior-agent`. Score is recomputed after each step; team correctness is visible immediately. This is a sequential scheduler, not simultaneous agent execution. Stochastic models, even with seeds, may not reproduce identical responses across runtimes or hardware. The run records inputs and outputs to support audit and replay, not a guarantee of deterministic model generation.

Not yet implemented: end-of-run contribution claims and their audit, statistical confidence intervals, aggregate token/cost reporting, resume, and a hardened sandbox. No actual model experiments have been run. Do not treat sample configuration sizes as calibrated scarcity; pilot the model first. Treat each team run as the experimental unit.

To exercise the full six-cell matrix with the **mock** policy:

```sh
python3 -m swarm_lab.batch --config configs/example.json --output runs/pilot --seeds 2 --scarce 6 --plentiful 18
```

The batch writes its randomized order to `schedule.json` and creates one directory per trial. Workloads draw from the same seeded generator but differ in size; the meaning of scarcity must be established by a pilot. Add `--model olmo-3:7b-instruct` to run the batch against a local Ollama server; first test a single run and calibrate workloads.

## Local open-weight models

Install and start [Ollama](https://ollama.com/download), then download a model yourself (the runner never downloads weights):

```sh
ollama pull olmo-3:7b-instruct
python3 -m swarm_lab.run --config configs/example.json --seed 42 --output runs/olmo-pilot --model olmo-3:7b-instruct
```

Additional candidate model names: `qwen3:8b`, `gpt-oss:20b`, and `mistral-small3.2:24b`. Their behavior and local compatibility have not been tested here. Mistral's package is about 15 GB, Olmo's about 4.5 GB; runtime and context need additional memory. Check available disk and memory before downloading. Run models one at a time on a 24 GB Mac. For formal experiments record the model digest (`ollama list`), Ollama version, quantization, OS and hardware alongside the manifest; tags may move. The model receives a JSON observation and returns one JSON action through Ollama's JSON output mode, not native function calling. Each response and full request are saved in the trajectory, including any thinking field provided by the runtime. Token counts and timing are present if returned by Ollama. Generation seed is recorded in each request; identical seeds do not guarantee bitwise identical outputs.

The default endpoint is `http://127.0.0.1:11434` and temperature is 0.6; override with `--ollama-url` and `--temperature`. Only use a trusted endpoint: observations and requests are sent to it. An API failure stops the run and marks its manifest failed. The partially written trajectory is preserved. No retries or resume are implemented. Invalid model JSON consumes an action and is retained in the raw provider response.

Each turn is a fresh model request containing the current shared board and scores, not a persistent chat transcript or private agent memory. This is a deliberate simplification and should be described when reporting results. The model is not shown prior private thoughts; the shared board displays prior authors and verification results. Pre-seeded tasks count as untouched for the overlap measure until a current agent acts on them.

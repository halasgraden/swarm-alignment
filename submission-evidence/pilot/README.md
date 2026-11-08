# Ranked incident-assistance pilot

Five completed team runs from the assistance-v6 pilot on task seed 900. This is the exploratory experiment presented in the video. Each run contains four agents and 18 action turns; the mixed team combines four model families, while each other team uses one family. These runs share a task seed and have no scoring or removal control. They do not establish a causal effect.

- `summary.json`: machine-exported run-level results.
- `seed900-*/trajectory.jsonl`: observations, responses, action events and checkpoint events. Raw provider exchanges have been removed.
- `seed900-*/reasoning.jsonl`: returned reasoning text for each action; explanations may be incomplete or incorrect and do not establish intent.
- `metrics.json` and `pre_checkpoint_metrics.json`: final and first-checkpoint measurements.

Model labels are pseudonyms; traces and reasoning may nevertheless make model identities inferable. The files include simulated incidents only. They omit raw provider exchanges, private task snapshots, private assignment mappings, manifests, usage records and older pilot runs. This is a curated evidence export, not a complete replay archive. See the study runbook for scenario details. The separately proposed credit-rule comparison uses a different protocol.

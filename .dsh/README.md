# `.dsh/`

Project-local DeepSeek Harness directory. DSH scans `.dsh/skills/` for
project-scoped skills; the files kept here are generated documentation
artifacts that belong with the project but not in the repository root.

| File | What it is |
|---|---|
| `evolvingworld_explained.html` | Self-contained interactive walkthrough of the framework: the paper, the two modules, persistent state, the data pipeline, simulation, evaluation, training, and the issues found while reading the code. |
| `training_curves.html` | Standalone viewer for LLaMA-Factory `trainer_log.jsonl` files: adaptive train/eval/loss panels, hover crosshair, wheel zoom, drag pan, log scale, PNG export. Ships with a synthetic sample dataset. |

Both are single-file HTML with no external dependencies — open them directly in
a browser.

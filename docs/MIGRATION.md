# Migration: scripts → uv package

The repository used to be a set of loose scripts that only worked when run from
the repository root. It is now an installable package. This document records what
moved, what changed, and how to update code that imported the old modules.

If you only ever ran the CLI commands, the [command table](#commands) is all you
need.

## Why

Three things were impossible before:

1. **`import` from anywhere.** `data_construction/utils.py` opened `config.json`
   at module scope, relative to the current working directory. Importing it from
   any other directory raised `FileNotFoundError`.
2. **`import` at all, for two modules.** `data_construction/main.py` and
   `transform.py` called `parse_args()` at module scope, so importing them parsed
   the *caller's* `sys.argv` and exited.
3. **Installing.** There was no `pyproject.toml`, no `requirements.txt`, and no
   `__init__.py` anywhere. `pip install -e .` had nothing to install.

## Layout

```
before                          after
──────────────────────────────  ──────────────────────────────────────────
data_construction/*.py      →   src/evolvingworld/data_construction/*.py
evaluation/*.py             →   src/evolvingworld/evaluation/*.py
simulation/*.py             →   src/evolvingworld/simulation/*.py
training/*.py               →   src/evolvingworld/training/*.py
(none)                      →   src/evolvingworld/config.py
(none)                      →   tests/
```

The `data_construction/`, `evaluation/`, `simulation/` and `training/`
directories still exist — they now hold the module READMEs, the shell launchers,
and the LLaMA-Factory YAML/DeepSpeed configs.

## Commands

| Before | After |
|---|---|
| `python simulation/main.py` | `evolvingworld-simulate` |
| `python evaluation/main.py` | `evolvingworld-evaluate` |
| `python data_construction/main.py` | `evolvingworld-build-data` |
| `python data_construction/split.py` | `evolvingworld-split-books` |
| `python data_construction/transform.py` | `evolvingworld-transform` |
| `python training/prepare_data.py` | `evolvingworld-prepare-data` |
| `python training/plot_training_log.py` | `evolvingworld-plot-log` |
| `python training/download_tulu3.py` | `evolvingworld-download-tulu3` |
| `python evaluation/generate_speaking_style_examples.py` | `evolvingworld-speaking-style` |

Every command also works as a module, which is useful when you want a specific
interpreter:

```bash
python -m evolvingworld.simulation.main --help
```

Arguments are unchanged. `--input`, `--mode`, `--max-scenes`, `--judge_model`
and the rest all behave exactly as before.

## Imports

The old modules were imported by bare name, which only worked because the script
directory was on `sys.path`:

| Before | After |
|---|---|
| `from utils import ...` (in `data_construction/`) | `from evolvingworld.data_construction.utils import ...` |
| `from split import split_book` | `from evolvingworld.data_construction.split import split_book` |
| `from data_loader import ...` (in `evaluation/`) | `from evolvingworld.evaluation.data_loader import ...` |
| `from judge import ...` | `from evolvingworld.evaluation.judge import ...` |
| `from aggregator import ...` | `from evolvingworld.evaluation.aggregator import ...` |
| `from prompts import ...` | `from evolvingworld.evaluation.prompts import ...` |
| `from inference import ...` (in `simulation/`) | `from evolvingworld.simulation.inference import ...` |
| `from simulator import ...` | `from evolvingworld.simulation.simulator import ...` |
| `from utils import ...` (in `simulation/`) | `from evolvingworld.simulation.utils import ...` |

Note that `data_construction/utils.py` and `simulation/utils.py` were both
imported as `utils`. Under the package they are distinct modules, so the
ambiguity is gone.

The `if __package__ is None: sys.path.insert(...)` blocks in `simulation/*` and
the `sys.path.insert(0, "evaluation")` call in `evaluation/main.py` are deleted.

## Configuration

Before, every entry point did:

```python
with open('config.json') as f:
    config = json.load(f)
```

Now `evolvingworld.config.load_config()` resolves credentials from the first
source that provides them:

1. an explicit `path` argument,
2. `$EVOLVINGWORLD_CONFIG`,
3. `./config.json`,
4. `~/.config/evolvingworld/config.json`,
5. `$EVOLVINGWORLD_API_KEY` and `$EVOLVINGWORLD_BASE_URL`.

Missing values become empty strings rather than raising, so importing the package
never requires credentials. `require_credentials()` raises a descriptive error at
the point where a request is actually made.

`config.json` in the repository root still works unchanged.

## Entry points

Each CLI is now a `main(argv=None)` function instead of a `if __name__ ==
'__main__':` block. This makes them callable from tests and from other code:

```python
from evolvingworld.simulation.main import main

main(["--input", "snapshots.json", "--mode", "local",
      "--world-base-url", "http://127.0.0.1:8000/v1",
      "--character-agent-base-url", "http://127.0.0.1:8001/v1"])
```

## Logs

Log files moved from the module directories to `logs/`:

| Before | After |
|---|---|
| `data_construction/main.log` | `logs/data_construction/main.log` |
| `data_construction/utils.log` | `logs/data_construction/utils.log` |

Handlers are attached in `main()` rather than at import time, so importing a
module no longer creates files.

## One behavioural fix

`data_construction/main.py` runs `process_book` through a `ProcessPoolExecutor`.
`process_book` reads the module-level `args`, and child processes re-import the
module — so `args` was unset in every worker.

This worked by accident under the `fork` start method, where the child inherits
the parent's memory. **Python 3.14 changed the Linux default to `forkserver`**,
where it does not.

The fix injects `args` explicitly:

```python
with ProcessPoolExecutor(
    max_workers=args.num_workers,
    initializer=_init_worker,
    initargs=(args,),
) as executor:
```

`args` is also now an `_UnsetArgs` proxy rather than `None`, so premature access
raises a descriptive `RuntimeError` instead of
`AttributeError: 'NoneType' object has no attribute 'model'`.

## If you had local patches

Re-apply them against `src/evolvingworld/...` and change the imports per the
table above. The two mechanical edits are:

```bash
# bare module imports → package imports
sed -i 's/^from utils import/from evolvingworld.data_construction.utils import/' \
    src/evolvingworld/data_construction/*.py
sed -i -E 's/^from (data_loader|judge|aggregator|prompts) import/from evolvingworld.evaluation.\1 import/' \
    src/evolvingworld/evaluation/*.py
```

Anything that touched `args` at module scope in `data_construction/main.py` or
`transform.py` needs to move inside `main()`.

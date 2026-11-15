# EvolvingWorld

This is the official repository for the paper ***"EvolvingWorld: An Open-Schema Framework for Co-Evolving Role-Play Agents and World Model in Interactive Literary World"***.

## 🎯 Overview

<img src="figure/pipeline.png" alt="EvolvingWorld framework pipeline" width="100%">

*Overview of the EvolvingWorld data construction, simulation, and evaluation pipeline.*

EvolvingWorld is an open-schema framework for simulating interactive literary worlds with two coupled components:

- **World Model**: plans scenes, selects locations and casts, proposes the next actor, and updates persistent global and location-level world state.
- **Character Agent**: generates character/environment interactions, updates character state, and infers motivations for upcoming scenes.

Key features:

- **Open-schema state modeling**: Character profiles and global world settings are constructed with book-specific dimensions and continue to evolve during simulation.
- **Character-world co-evolution**: Character actions can change global or location-level world states, while world changes can affect character motivations and profiles.
- **Long-horizon simulation**: The simulation rolls forward scene by scene while persistently evolving character and world states, enabling coherent long-horizon trajectories.
- **Multi-timescale character evolution**: Hidden trackers record weak or emerging evidence before profile updates, supporting dimensions that evolve at different speeds, from short-term emotional shifts to slower personality changes.

This repository includes the processed dataset, data construction scripts, SFT utilities, simulation pipeline, and trajectory-level evaluation framework.

## 📚 Table of Contents

- [Overview](#overview)
- [Repository Structure](#repository-structure)
- [Documentation](#documentation)
- [Quick Start](#quick-start)
  - [Preparation](#1-preparation)
  - [Simulation](#2-simulation)
  - [Evaluation](#3-evaluation)
- [Training](#training)
- [Constructing Your Own Dataset](#constructing-your-own-dataset)
- [Known Issues](#known-issues)
- [Citation](#citation)

## 🗂️ Repository Structure

```text
EvolvingWorld/
├── pyproject.toml        # uv project definition: deps, extras, console scripts
├── uv.lock               # Pinned dependency lockfile
├── config.json           # API credentials (api_key / base_url)
├── src/evolvingworld/    # The installable package
│   ├── config.py         # Credential resolution (file / env var)
│   ├── data_construction/# Pipeline for constructing extracted data and training/test files
│   ├── simulation/       # Two-model interactive simulation pipeline
│   ├── evaluation/       # LLM-as-judge evaluation framework
│   └── training/         # LLaMA-Factory data prep and log plotting
├── tests/                # Packaging and helper tests (no network)
├── docs/                 # Architecture, migration, reproduction, known issues
├── dataset/              # Released dataset: extracted data, SFT data, and test snapshots
├── figure/               # README and paper figures
├── training/             # LLaMA-Factory configs and shell launchers
├── data_construction/    # Module README
├── simulation/           # Module README
└── evaluation/           # Module README + batch eval script
```

Each major module has its own README with detailed commands:

- `data_construction/README.md`
- `training/README.md`
- `simulation/README.md`
- `evaluation/README.md`

### Console scripts

`uv sync` installs these entry points:

| Command | Purpose |
|---|---|
| `evolvingworld-simulate` | Roll a story forward from test snapshots |
| `evolvingworld-evaluate` | LLM-as-judge trajectory evaluation |
| `evolvingworld-build-data` | Extract structured book data from raw books |
| `evolvingworld-split-books` | Split raw books into chapter segments |
| `evolvingworld-transform` | Build SFT training files and test snapshots |
| `evolvingworld-prepare-data` | Prepare LLaMA-Factory datasets |
| `evolvingworld-plot-log` | Plot training curves from `trainer_log.jsonl` |
| `evolvingworld-download-tulu3` | Download and convert the Tulu3 SFT mixture |
| `evolvingworld-speaking-style` | Sample per-character speaking-style examples |

Every command also works as a module, e.g. `python -m evolvingworld.simulation.main`.

## 📖 Documentation

| Document | Contents |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | The two modules, the seven tasks, persistent state, thought masking, the simulation loop, the evaluation structure |
| [docs/REPRODUCING.md](docs/REPRODUCING.md) | Paper protocol vs repository defaults, full command sequences, training hyperparameters |
| [docs/MIGRATION.md](docs/MIGRATION.md) | What changed when the scripts became a uv package, and how to update code that imported the old modules |
| [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md) | 24 issues found while reading the code, ranked by impact, with file and line references |

## 🚀 Quick Start

### 🛠️ 1. Preparation

**Install the package with [uv](https://docs.astral.sh/uv/).**

EvolvingWorld is a standard `uv` project (`pyproject.toml` + `uv.lock`). The core
install covers data construction, simulation and evaluation:

```bash
git clone https://github.com/HKUST-KnowComp/EvolvingWorld.git
cd EvolvingWorld
uv sync
```

Optional extras:

```bash
uv sync --extra serve     # local vLLM serving
uv sync --extra train     # LLaMA-Factory SFT pipeline (pulls torch/transformers)
uv sync --extra dev       # pytest + ruff
```

`uv sync` creates `.venv/` and installs the `evolvingworld` package in editable
mode, so every command below is available as a console script. Prefix them with
`uv run` (e.g. `uv run evolvingworld-simulate ...`) or activate the environment
first:

```bash
source .venv/bin/activate
```

Run the test suite (no network, no credentials required):

```bash
uv run pytest -q
```

The training pipeline uses LLaMA-Factory, which is heavy and best kept in its own
environment:

```bash
uv venv .venv-train --python 3.10
uv pip install --python .venv-train/bin/python -e ".[train]"
```

Unless otherwise stated, run commands from the `EvolvingWorld/` project root.

**Configure API access.**

Scripts that call an OpenAI-compatible endpoint read credentials from the first
source that provides them:

1. `$EVOLVINGWORLD_CONFIG` — path to a JSON file,
2. `./config.json` in the current working directory,
3. `~/.config/evolvingworld/config.json`,
4. `$EVOLVINGWORLD_API_KEY` and `$EVOLVINGWORLD_BASE_URL`.

The simplest option is a `config.json` in the project root:

```json
{
  "api_key": "YOUR_API_KEY",
  "base_url": "YOUR_BASE_URL"
}
```

**Download the dataset.**

The processed [EvolvingWorld dataset](https://huggingface.co/datasets/zongqing0068/EvolvingWorld) is hosted on Hugging Face:

```bash
hf download zongqing0068/EvolvingWorld \
  --repo-type dataset \
  --local-dir dataset
```

The dataset contains:

- `dataset/extracted_data/scenes/`: standardized scene data with summaries, scenarios, interactions, character lists, and location lists.
- `dataset/extracted_data/character_dynamic/`: dynamic character profiles, motivations, short descriptions, and hidden trackers.
- `dataset/extracted_data/world_dynamic/`: dynamic global and location-level world states.
- `dataset/train/`: ShareGPT-style supervised training files for the World Model and Character Agent.
- `dataset/test/`: simulation starting snapshots and speaking-style examples for evaluation.

`dataset/original_books_from_gutenberg.jsonl` is an example file that demonstrates the expected raw-book input format. Each JSONL row should contain `title`, `author`, and `content` fields.

### 🎮 2. Simulation

Run one test snapshot with remote API models:

```bash
evolvingworld-simulate \
  --input dataset/test/test_all.json \
  --mode remote \
  --world-model gemini-2.5-pro \
  --character-agent-model gemini-2.5-pro \
  --offset 0 --limit 1 \
  --output-dir simulation/outputs/example_run
```

For local vLLM serving, more detailed running instructions, and parameter descriptions, see `simulation/README.md`.

### 📊 3. Evaluation

```bash
bash evaluation/run_all_eval.sh --judge gemini-2.5-pro example_run
```

We introduce two score families for trajectory-level evaluation: **CHARACTER** metrics for character consistency, evolution quality, environmental grounding, interaction quality, motivation generation, and instruction compliance; and **WORLD** metrics for scene planning, speaker management, world-state maintenance, and instruction compliance.

See `evaluation/README.md` for detailed evaluation usage, input/output formats, and metric definitions.

## 🧠 Training

Training uses LLaMA-Factory. The World Model and Character Agent are trained separately (distinguished as `model_a` and `model_b` in code).

First ensure the task-level data files exist under `dataset/train/`, then run:

```bash
# Train the World Model (--model model_a)
bash training/run.sh --model model_a --mode full --gpu 0 \
  --model-name-or-path Qwen/Qwen2.5-7B-Instruct

# Train the Character Agent (--model model_b)
bash training/run.sh --model model_b --mode full --gpu 1 \
  --model-name-or-path Qwen/Qwen2.5-7B-Instruct
```

Training hyperparameters are configured in `training/train_config.yaml`. See `training/README.md` for detailed training instructions.

## 📦 Constructing Your Own Dataset

To construct an EvolvingWorld-style dataset from your own books or other fictional works, first prepare a JSONL file where each line is a book record:

```json
{"title": "Pride and Prejudice", "author": "Jane Austen", "content": "..."}
{"title": "The Picture of Dorian Gray", "author": "Oscar Wilde", "content": "..."}
```

`dataset/original_books_from_gutenberg.jsonl` is the default input path used by the construction script. To construct your own dataset, replace this file with the raw text of the books you want to process. Alternatively, you can use the source-book JSONL provided in [`EvolvingWorld-Books-Gutenberg`](https://huggingface.co/datasets/zongqing0068/EvolvingWorld-Books-Gutenberg), which follows the same format and contains the source books used for constructing EvolvingWorld.

Then run the two-stage construction pipeline.

```bash
# Step 1: extract structured book data
evolvingworld-build-data \
  --input dataset/original_books_from_gutenberg.jsonl \
  --output_dir data \
  --num_workers 8 \
  --model gemini-2.5-pro \
  --candidate_model claude-sonnet-4-5

# Step 2: build training and test data
evolvingworld-transform \
  --dir dataset/extracted_data \
  --seed 40
```

See `data_construction/README.md` for detailed pipeline instructions and parameter descriptions.

## ⚠️ Known Issues

A full read of the codebase turned up 24 issues. The three that matter most:

1. **`hidden_tracker` timing leak** — the evaluation reads the tracker *after* the
   scene it is scoring but labels it "at scene start", which inflates PF, SSF and
   MDB.
2. **Non-reproducible scene sampling** — `random.sample` for per-metric scene
   selection is unseeded, so re-running a sample yields different scores.
3. **`lang_detect` always returns `'en'`** — the field it inspects is stripped
   upstream, so world cards for non-English books are generated in English.

See [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md) for the full list with file and
line references, and [docs/REPRODUCING.md](docs/REPRODUCING.md) for the
parameters you must pass to match the paper's protocol.

## 📝 Citation

If you use EvolvingWorld, please cite:

```text
EvolvingWorld: An Open-Schema Framework for Co-Evolving Role-Play Agents and World Model in Interactive Literary World
```


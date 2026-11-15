# Reproducing the paper

The repository defaults are **not** the paper's protocol. This document lists the
parameters you must pass explicitly, and the known deviations that will move your
numbers away from the published ones.

## 1. Dataset

The processed dataset is not in the repository. Download it first:

```bash
hf download zongqing0068/EvolvingWorld \
  --repo-type dataset \
  --local-dir dataset
```

Expected layout:

```
dataset/
├── extracted_data/
│   ├── scenes/            # per-book scene files
│   ├── character_dynamic/ # profile / motivation / hidden-tracker history
│   └── world_dynamic/     # global and location-level state history
├── train/                 # ShareGPT SFT files, one per task
└── test/
    ├── test_all.json      # 222 simulation start snapshots
    └── speaking_style_examples.json
```

The paper's corpus: 57 books, 9,763 scenes, 132,800 interactions, 3,311
characters, 1,888 locations, 138,596 training samples, 222 test snapshots
(116 in-distribution, 106 out-of-distribution).

## 2. Simulation

**The default is 5 scenes × 12 turns. The paper uses 20 scenes × 50
interactions.** Pass both explicitly or you will not reproduce anything:

```bash
evolvingworld-simulate \
  --input dataset/test/test_all.json \
  --mode remote \
  --world-model gemini-2.5-pro \
  --character-agent-model gemini-2.5-pro \
  --max-scenes 20 \
  --max-turns-per-scene 50 \
  --num-workers 8 \
  --output-dir simulation/outputs/paper_run
```

For a locally served checkpoint, use two vLLM endpoints:

```bash
CUDA_VISIBLE_DEVICES=0 vllm serve <checkpoint> --port 8000 --served-model-name world-model
CUDA_VISIBLE_DEVICES=1 vllm serve <checkpoint> --port 8001 --served-model-name character-agent

evolvingworld-simulate \
  --input dataset/test/test_all.json \
  --mode local \
  --world-base-url http://127.0.0.1:8000/v1 \
  --character-agent-base-url http://127.0.0.1:8001/v1 \
  --max-scenes 20 --max-turns-per-scene 50 \
  --max-tokens 8192 \
  --output-dir simulation/outputs/paper_run
```

`--max-tokens` defaults to 16384. Lower it for models with a 32K context window,
otherwise prompt plus completion can overflow.

## 3. Evaluation

```bash
evolvingworld-evaluate \
  --input_dir simulation/outputs/paper_run \
  --input_snapshots dataset/test/test_all.json \
  --judge_model gemini-2.5-pro \
  --num_workers 8 \
  --output_dir evaluation/results/paper_run
```

`--input_snapshots` is required: the judge needs the original snapshot as the
`scene_index = 0` reference for profiles and world state.

Each metric samples **7 scenes** (`SCENES_PER_METRIC` in
`evaluation/main.py`). With 20 metrics that is roughly 140 judge calls per
sample.

## 4. Training

```bash
uv sync --extra train
bash training/run.sh --model model_a --mode full --gpu 0
bash training/run.sh --model model_b --mode full --gpu 1
```

The shipped `training/train_config.yaml` matches the paper:

| Parameter | Value |
|---|---|
| Base model | `meta-llama/Llama-3.1-8B-Instruct` |
| Method | LoRA, `r=64`, `α=128`, `dropout=0.05`, `target=all` |
| Epochs | 2 |
| Learning rate | `2e-5`, cosine, `warmup_ratio=0.1` |
| Cutoff | 32768 |
| Batch | `per_device=1` × `grad_accum=64` |
| Precision | bf16, FlashAttention 2 |
| Eval holdout | 10% |

> **Watch out**: `train_config.yaml` sets `packing: true`, but
> `training/run.sh` hardcodes `PACKING=false` and passes it on the command line,
> which wins. If you invoke `llamafactory-cli` directly from the YAML you will
> get packing enabled — a different run.

## 5. Known deviations

These will move your numbers relative to the published table. See
[KNOWN_ISSUES.md](KNOWN_ISSUES.md) for detail.

| Issue | Effect |
|---|---|
| `hidden_tracker` read post-scene but labelled "at scene start" | Inflates **PF**, **SSF**, **MDB**; weakens the hidden-tracker ablation |
| Unseeded `random.sample` for per-metric scene selection | Scores vary between runs on the same sample |
| All-or-nothing `compute_final_scores` | One exhausted judge retry drops the whole sample from the mean |
| `lang_detect` always returns `'en'` | World cards for non-English books are generated in English |

The first two are the ones to fix before trusting a reproduction attempt.

## 6. Sanity check

Before spending GPU hours, confirm the package is wired correctly:

```bash
uv run pytest -q
```

40 tests, no network, no credentials required.

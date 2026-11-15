# Architecture

EvolvingWorld simulates an interactive literary world with two coupled language
models: a **World Model** that directs the story, and a **Character Agent** that
plays every character in it. Both are fine-tuned on the same corpus and both
read and write a persistent state that survives across scenes.

```
                    ┌──────────────────────────────┐
                    │        World Model           │
                    │  plans scenes, casts,        │
                    │  locations, world updates    │
                    └───────────┬──────────────────┘
                                │  scene plan
                                ▼
                    ┌──────────────────────────────┐
                    │      Character Agent         │
                    │  plays every character,      │
                    │  updates character state     │
                    └───────────┬──────────────────┘
                                │  interactions
                                ▼
                    ┌──────────────────────────────┐
                    │      Persistent State        │
                    │  S_w = (G, L)   S_c = (P,H,M)│
                    └──────────────────────────────┘
```

## The two modules

| | World Model (`model_a`) | Character Agent (`model_b`) |
|---|---|---|
| Role | Director / environment | Actor |
| Decides | What happens next, where, to whom | What each character says and does |
| Writes | Global and location-level world state | Character profile, hidden tracker, motivation |
| Tasks | 4 | 3 |

The split matters because the two roles need different information. The World
Model sees the whole cast and the world state; the Character Agent sees only what
its character could plausibly know (see [Thought masking](#thought-masking)).

## The seven tasks

Every task is a separate supervised example. `data_construction/transform.py`
emits them; `simulation/simulator.py` calls them at inference time.

### World Model

| Task | Input | Output |
|---|---|---|
| `scene_cast` | Global state, character descriptions, previous scene | `has_next_scene`, `involved_characters` |
| `location_scenario` | Global state, selected cast | `location`, `scenario` |
| `next_character` | Scene so far, cast | Next speaker, or end of scene |
| `world_update` | Scene so far | `update_global`, `update_location` deltas |

### Character Agent

| Task | Input | Output |
|---|---|---|
| `interaction_gen` | Character's own state, masked scene history | `[thought] speech (action)` |
| `character_update` | Scene the character participated in | Updated profile, short description, hidden tracker |
| `motivation_update` | Next scene's cast, location, scenario | Motivation for the upcoming scene |

## Persistent state

State is the only thing that survives a scene boundary. It is deliberately
open-schema: the dimensions are discovered per book rather than fixed globally.

### World state — `S_w = (G, L)`

- **`G`** — global state: era, social order, ongoing events, anything book-wide.
- **`L`** — per-location state: one card per location, plus a prose description.

Both are versioned. `world_update` returns deltas, and the simulation applies
them to the live state; the evaluation reads the resulting history.

### Character state — `S_c = (P, H, M)`

- **`P`** — profile: the stable, visible facts about a character.
- **`H`** — hidden tracker: weak or emerging evidence that has not yet crossed
  the threshold into `P`.
- **`M`** — motivation: what the character wants in the *next* scene.

### Why the hidden tracker exists

Characters change at different speeds. A short-term emotional shift should not
immediately rewrite a personality trait, but it should not be discarded either.
`H` accumulates weak signals across scenes; when enough evidence accumulates, the
`character_update` task promotes it into `P`.

This is the multi-timescale part of the paper: `H` is the slow buffer, `P` is the
committed state, and the promotion threshold is learned rather than hand-set.

> **Caveat**: the evaluation currently reads `H` *after* the scene it is scoring
> while labelling it "at scene start". See
> [KNOWN_ISSUES.md #1](KNOWN_ISSUES.md#1-hidden_tracker-is-read-after-the-scene-but-labelled-at-scene-start).

## Simulation loop

`StorySimulator.run_snapshot` (`simulation/simulator.py`) runs one snapshot:

```
for scene in range(max_scenes):
    scene_cast          → has_next_scene? cast?
    location_scenario   → where, and what happens
    motivation_update   → why each character is there
    ┌─ execution loop ─────────────────────────────┐
    │  next_character  → who acts                  │
    │  interaction_gen → what they say and do      │
    │  world_update    → did the world change?     │
    └──────────────────────────────────────────────┘
    character_update    → reflect on the scene
```

The loop stops on `story_finished`, `max_scenes_reached`, or `error`. Each
interaction turn fires the `on_progress` callback, which is what makes the
file-based progress polling in `simulation/main.py` work.

## Thought masking

Interactions are written as:

```
[thought] speech (action)
```

The bracketed thought is private. Before a character's context is assembled,
`remove_other_character_thoughts` (`simulation/utils.py`) strips every `[...]`
block, so a character never sees another character's inner monologue. The
character's own thoughts are preserved.

This is the mechanism that keeps the simulation from collapsing into omniscience:
without it, every character would react to information they should not have.

## Segment split

Training data cuts the conversation whenever `world_update` changes state — the
new state is baked into the system prompt and the turn history resets. The
simulation mirrors this exactly (`simulation/simulator.py`, the
`world_update.get("update_global") or world_update.get("update_location")` check
inside `run_scene_execution`).

Without the mirror, inference would see a conversation shape the model never saw
during training.

## Evaluation

Trajectory-level, LLM-as-judge, reference-free. Twenty sub-metrics in two
families:

| Family | Metrics | Count |
|---|---|---|
| CHARACTER | `PF` `SSF` `MDB` `PUF` `EA` `EU` `CR` `NP` `MQ` `IC_char` `PES` | 11 |
| WORLD | `CSR` `LSR` `TSO` `GUS` `GSA` `LUS` `LSA` `IC_world` `SCC` | 9 |

Each metric is scored independently: the judge returns `merits` and `demerits`
with point values, and the code computes `50 + Σmerits − Σdemerits`, clamped to
`[0, 100]`. A sample's CHARACTER score is the mean of its 11 CHARACTER metrics;
the WORLD score is the mean of its 9.

Two penalties apply on top:

- **IC penalty** — `min(50, 50 / ln(n + 1))` where `n` is the number of model
  calls, for instruction-compliance failures.
- **Task penalty** — `avg × N / (N + 1)` for error samples, equivalent to adding
  one zero-scored scene.

See `evaluation/README.md` for the full metric definitions.

## Data pipeline

```
raw books (JSONL)
  → split.py            chapter / main-content segmentation
  → main.py             13 extraction stages → structured scenes, characters, world
  → transform.py        ShareGPT SFT files + test snapshots
```

Each stage caches to disk and is resumable. See
`data_construction/README.md` for the stage list and
[KNOWN_ISSUES.md](KNOWN_ISSUES.md) for the caveats.

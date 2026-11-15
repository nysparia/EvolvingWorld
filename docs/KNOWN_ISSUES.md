# Known Issues

Findings from a full read of the codebase, cross-checked against the paper and
against the repository's own documentation.

Line numbers are accurate as of commit `6351133`. Prefer the named function when
a reference has drifted — the code moves, the function names do not.

Three of the 24 are documentation drift and are marked **Status: fixed** inline;
the rest are open. The [last section](#fixed-in-this-fork) lists what the uv
packaging work already resolved.

Severity:

| Level | Meaning |
|---|---|
| **High** | Changes reported numbers, or silently produces wrong results |
| **Medium** | Breaks under specific conditions, or wastes significant compute |
| **Low** | Maintainability, dead code, documentation drift |

---

## High

### 1. `hidden_tracker` is read after the scene but labelled "at scene start"

`evaluation/data_loader.py:721` pulls `hidden_tracker` from the scene's
`scene_description`, which is written by the **post-scene** reflection step.
`evaluation/prompts.py:1183` then labels the block:

```
## Character Hidden Trackers (at scene start)
```

The judge therefore sees the tracker state that *resulted from* the scene it is
scoring. This leaks the outcome into the input for the three metrics that depend
on it — **PF**, **SSF**, **MDB** — and systematically inflates them.

It also weakens the paper's hidden-tracker ablation: the "w/o hidden tracker" arm
removes a signal that was partly redundant with the answer.

**Fix direction**: snapshot the tracker *before* the scene (the simulation already
carries `character_states[name]["hidden_tracker"]` at scene start), or relabel
the block and accept that the metric measures post-hoc consistency.

### 2. Scene sampling is not reproducible

`evaluation/main.py:381`:

```python
sampled = random.sample(all_scene_indices, SCENES_PER_METRIC)
```

`SCENES_PER_METRIC = 7` (`evaluation/main.py:363`). The global `random` module is
never seeded for this call — `--sample_seed` only controls `--sample_ratio`
sample selection, not per-metric scene selection.

Re-running the same sample evaluates a different set of 7 scenes, so scores move
between runs. `--resume` skips completed samples but cannot reproduce a score
that was already written.

**Fix direction**: derive the RNG from `(sample_seed, sample_name, metric_name)`.

### 3. `lang_detect` always returns `'en'`

`data_construction/utils.py:363` inspects its argument; every caller passes
`scenes[0].get('text', '')[:100]` (`data_construction/main.py:1277, 1951, 2222,
3209, 3703`).

But `text` is one of the fields removed by `remove_private_scene_fields()`
(`data_construction/main.py:82-93`) before those stages run. The call therefore
always receives `''` and falls through to `'en'`.

Consequence: world cards for Chinese books are requested in English.

**Fix direction**: detect language from a field that survives, or capture it
during extraction and store it on the book record.

---

## Medium — data construction

### 4. `restore_from_cache` is dead code

`data_construction/main.py:978`, called at `4219` immediately after `extract()`.
Its guard is "skip if the output file already exists", which `extract()` has just
made true. Even bypassing that, the cache filter requires
`model == 'claude-3-5-sonnet-20240620'` and a prompt prefix that no longer exists.

### 5. Stages are coupled by function name

`data_construction/utils.py:1383`:

```python
if post_processing_func.__name__ == 'parse_response' and response == False:
```

Renaming `parse_response` silently disables the backup-retry path for every
caller. Nothing fails; the retry just stops happening.

### 6. 11 of 13 stages swallow their own exceptions

`process_book` (`data_construction/main.py:4208`) calls 13 stages and checks only
the return value of the last one (`world_dynamic`, line 4231). Every stage
returns `book['title']` on failure — a truthy value — so a mid-pipeline failure
still logs `Successfully processed book: ...`.

### 7. The cache key embeds the whole book

`data_construction/utils.py:196` (`cached`) builds
`key = (func.__name__, str(args), str(kwargs.items()))`. For book-level calls
`args[0]` is the full book dict, so every miss rewrites a pickle containing the
entire corpus. Cost grows quadratically with cache size.

### 8. Prompt-style variants are unreachable in data construction

`build_diverse_task_prompt` hardcodes `style='plain'`
(`data_construction/utils.py:475, 500`), and `set_book_prompt_style()` has no
call site anywhere in the repository. The `=` / `#` / `*` heading decorations
exist in the code but are only reachable from the simulation path.

### 9. Hardcoded model names

`data_construction/utils.py:1214` and `1337` pin `claude-3-5-sonnet-2.0` for JSON
repair and refusal rewriting, ignoring `--model`.

### 10. `split.py` crashes on the JSON-repair path

`extract_json(response)` is called without `model=` at
`data_construction/split.py:85, 110, 214, 238`. Reaching the LLM-repair branch
raises `KeyError`.

---

## Medium — evaluation

### 11. All-or-nothing scoring

`compute_final_scores` (`evaluation/aggregator.py:303`) returns `None` for the
whole CHARACTER or WORLD score if **any** constituent metric is `None`. With
roughly 140 judge calls per sample, one exhausted retry removes the entire sample
from the mean.

### 12. Score parsing is fragile

`evaluation/judge.py:249`:

```python
m["points"] = abs(m["points"])
```

A string or `None` raises `TypeError`, which propagates to the sample-level
`except` and fails the whole sample.

### 13. Empty merits/demerits silently score 50

`evaluation/judge.py:259` computes `50 + sum(merits) - sum(demerits)`. A response
with no merits and no demerits passes validation and scores exactly 50, which is
indistinguishable from a genuine neutral judgement.

### 14. The IC penalty's `n` is estimated, not counted

`compute_error_ic_penalty` (`evaluation/data_loader.py:310`) reconstructs the
call count from scene structure. The paper describes `n` as the *total number of
calls*, and `trace.json` would hold the real number — but it is never written
(see #19).

### 15. Penalty post-processing ignores the sample filter

`evaluation/main.py:950-965` walks every `sample_*_eval.json` in `--output_dir`,
including samples excluded by `--samples` or `--sample_ratio`.

### 16. Metric lists are defined twice

`evaluation/aggregator.py:22-31` and `evaluation/prompts.py:1462-1466` each carry
their own copy of the CHARACTER and WORLD metric names. Editing one and not the
other silently changes what gets averaged.

---

## Low — maintainability

### 17. `ground_truth_scenes` is dead data

`data_construction/transform.py:1146-1163` builds up to five ground-truth scenes
and stores them on every test snapshot. Nothing in `simulation/` or
`evaluation/` ever reads them — evaluation is entirely reference-free.

### 18. `_kill_child_processes` is POSIX-only

`simulation/main.py:347-363` shells out to `pgrep` / `pkill`. On Windows the
fallback path is a no-op, so Ctrl-C leaves orphaned workers.

### 19. `trace.json` is documented but never written

`simulation/README.md:146` lists `trace.json` in the per-sample output tree.
`grep -rn "trace.json" src/` returns nothing — the trace is built in memory
(`StorySimulator.run_snapshot` returns it) and then discarded by
`run_single_sample`, which keeps only `result`.

**Status**: documentation fixed — `simulation/README.md` now states that no
`trace.json` is written and points at `--log-model-io` instead. The code is
unchanged.

### 20. `config.json` is tracked but not ignored

`config.json` is committed with empty values and is absent from `.gitignore`.
Filling in a real key makes it show up as `modified`, one `git add .` away from
being committed.

**Fix direction**: commit `config.example.json`, ignore `config.json`, and rely
on `evolvingworld.config` (which already supports `$EVOLVINGWORLD_CONFIG` and
`$EVOLVINGWORLD_API_KEY` / `$EVOLVINGWORLD_BASE_URL`).

---

## Documentation drift

### 21. Evaluation output structure is incomplete

`evaluation/README.md:109-119` documents only `sample_N_eval.json`. The code also
writes `sample_N_penalized.json` (`evaluation/main.py:965`), and the summary is
built from the penalized files with the eval files as fallback
(`evaluation/main.py:1007`).

**Status**: fixed — `evaluation/README.md` now lists both files and says which
one the summary reads.

### 22. The task penalty is undocumented

`compute_task_penalty` (`evaluation/aggregator.py:202`) applies
`avg × N / (N+1)` to the metric named in `error_attribution`. The paper describes
it; the README does not.

**Status**: fixed — the formula and its two cases are now in
`evaluation/README.md`.

### 23. Worker-count defaults disagree

`evaluation/main.py:128` defaults `--num_workers` to 8;
`evaluation/run_all_eval.sh:8` defaults `NUM_WORKERS=100`.

### 24. Repository defaults are not the paper protocol

`simulation/main.py:48-49` defaults to `--max-scenes 5 --max-turns-per-scene 12`.
The paper evaluates with **20 scenes / 50 interactions**. Reproducing the paper
requires passing both explicitly. See [REPRODUCING.md](REPRODUCING.md).

---

## Fixed in this fork

| Issue | Fix |
|---|---|
| No dependency manifest | `pyproject.toml` + `uv.lock` |
| Zero tests | `tests/test_package.py` (40 tests) |
| `sys.path.insert` shims and `__package__` dual-import blocks | Absolute `evolvingworld.*` imports |
| `parse_args()` at import time | Moved into `main(argv=None)` |
| `open('config.json')` at import time, relative to cwd | `evolvingworld.config.load_config()` |
| `import __main__` (unused) | Removed |
| `ProcessPoolExecutor` children losing the `args` global under `forkserver` / `spawn` | `initializer=_init_worker` |
| `matplotlib` imported at module scope | Imported inside `plot_rows` |

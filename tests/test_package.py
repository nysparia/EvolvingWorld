"""Packaging smoke tests for EvolvingWorld.

These tests do not touch the network.  They verify that the package is
importable, that credentials resolve from every documented source, and that
every console script points at a real callable.
"""

from __future__ import annotations

import importlib
from importlib.metadata import entry_points

import pytest

MODULES = [
    "evolvingworld",
    "evolvingworld.config",
    "evolvingworld.data_construction.utils",
    "evolvingworld.data_construction.split",
    "evolvingworld.data_construction.transform",
    "evolvingworld.data_construction.main",
    "evolvingworld.evaluation.data_loader",
    "evolvingworld.evaluation.prompts",
    "evolvingworld.evaluation.aggregator",
    "evolvingworld.evaluation.judge",
    "evolvingworld.evaluation.main",
    "evolvingworld.evaluation.generate_speaking_style_examples",
    "evolvingworld.simulation.utils",
    "evolvingworld.simulation.inference",
    "evolvingworld.simulation.simulator",
    "evolvingworld.simulation.main",
    "evolvingworld.training.prepare_data",
    "evolvingworld.training.plot_training_log",
    "evolvingworld.training.download_tulu3",
]

CONSOLE_SCRIPTS = [
    "evolvingworld-simulate",
    "evolvingworld-evaluate",
    "evolvingworld-build-data",
    "evolvingworld-split-books",
    "evolvingworld-transform",
    "evolvingworld-prepare-data",
    "evolvingworld-plot-log",
    "evolvingworld-download-tulu3",
    "evolvingworld-speaking-style",
]


@pytest.mark.parametrize("module", MODULES)
def test_module_imports(module: str) -> None:
    """Importing a module must not require credentials or a specific cwd."""
    assert importlib.import_module(module) is not None


@pytest.mark.parametrize("script", CONSOLE_SCRIPTS)
def test_console_script_target_is_callable(script: str) -> None:
    eps = {ep.name: ep for ep in entry_points(group="console_scripts")}
    assert script in eps, f"{script} is not registered"
    assert callable(eps[script].load()), f"{script} does not resolve to a callable"


def test_config_has_expected_keys() -> None:
    from evolvingworld.config import load_config

    cfg = load_config()
    assert "api_key" in cfg
    assert "base_url" in cfg
    assert isinstance(cfg["api_key"], str)
    assert isinstance(cfg["base_url"], str)


def test_config_reads_explicit_file(tmp_path) -> None:
    from evolvingworld.config import load_config

    path = tmp_path / "creds.json"
    path.write_text('{"api_key": "sk-explicit", "base_url": "https://explicit/v1"}', encoding="utf-8")

    cfg = load_config(path)
    assert cfg["api_key"] == "sk-explicit"
    assert cfg["base_url"] == "https://explicit/v1"


def test_config_missing_explicit_file_raises(tmp_path) -> None:
    from evolvingworld.config import load_config

    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "nope.json")


def test_config_env_var_fallback(monkeypatch) -> None:
    from evolvingworld.config import API_KEY_ENV_VAR, BASE_URL_ENV_VAR, load_config

    monkeypatch.setenv(API_KEY_ENV_VAR, "sk-from-env")
    monkeypatch.setenv(BASE_URL_ENV_VAR, "https://env/v1")
    monkeypatch.chdir("/")

    cfg = load_config()
    assert cfg["api_key"] == "sk-from-env"
    assert cfg["base_url"] == "https://env/v1"


def test_require_credentials_raises_when_empty() -> None:
    from evolvingworld.config import require_credentials

    with pytest.raises(RuntimeError, match="No API credentials configured"):
        require_credentials({"api_key": "", "base_url": ""})


def test_require_credentials_returns_pair() -> None:
    from evolvingworld.config import require_credentials

    assert require_credentials({"api_key": "k", "base_url": "u"}) == ("k", "u")


def test_strip_chatcompletions_suffix() -> None:
    from evolvingworld.simulation.utils import strip_chatcompletions_suffix

    assert strip_chatcompletions_suffix("http://127.0.0.1:8000/v1/chat/completions") == "http://127.0.0.1:8000/v1"
    assert strip_chatcompletions_suffix("http://127.0.0.1:8000/v1") == "http://127.0.0.1:8000/v1"


def test_remove_other_character_thoughts() -> None:
    from evolvingworld.simulation.utils import remove_other_character_thoughts

    text = "[Alice]: [secret plan] Hello there. (waves)"
    cleaned = remove_other_character_thoughts(text)
    assert "secret plan" not in cleaned
    assert "Hello there." in cleaned
    assert "(waves)" in cleaned


def test_build_diverse_task_prompt_renders_sections() -> None:
    from evolvingworld.data_construction.utils import build_diverse_task_prompt

    prompt = build_diverse_task_prompt(
        ["You are a director."],
        ["Plan the next scene."],
        [("world_state", "current world")],
        [("scene_cast", "list of characters")],
    )
    assert "Plan the next scene." in prompt
    assert "scene_cast" in prompt


def test_simulation_config_defaults() -> None:
    from evolvingworld.simulation.simulator import SimulationConfig

    cfg = SimulationConfig(max_scenes=20, max_turns_per_scene=50)
    assert cfg.max_scenes == 20
    assert cfg.max_turns_per_scene == 50
    assert cfg.max_tokens == 16384


def test_data_construction_args_guard() -> None:
    """Accessing ``args`` before ``main()`` must fail with a clear message."""
    from evolvingworld.data_construction import main as dc_main

    with pytest.raises(RuntimeError, match="args is not initialised"):
        _ = dc_main.args.model


def test_data_construction_worker_initializer() -> None:
    """The ProcessPoolExecutor initializer must inject ``args`` into children."""
    import argparse

    from evolvingworld.data_construction import main as dc_main

    sentinel = argparse.Namespace(model="sentinel-model", output_dir="/tmp/x")
    dc_main._init_worker(sentinel)
    try:
        assert dc_main.args.model == "sentinel-model"
    finally:
        dc_main.args = dc_main._UnsetArgs()

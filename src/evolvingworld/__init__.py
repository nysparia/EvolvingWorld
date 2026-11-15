"""EvolvingWorld.

An open-schema framework for co-evolving role-play agents and a world model in
interactive literary worlds.

The package is organised into four sub-packages that mirror the paper's
pipeline:

``evolvingworld.data_construction``
    Build extracted book data, SFT training files and test snapshots.
``evolvingworld.simulation``
    Roll a story forward scene by scene with a World Model and a Character
    Agent.
``evolvingworld.evaluation``
    LLM-as-judge trajectory evaluation (CHARACTER / WORLD scores).
``evolvingworld.training``
    LLaMA-Factory data preparation and training-log plotting helpers.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__", "config"]

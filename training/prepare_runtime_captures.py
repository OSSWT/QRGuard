"""Compatibility entry point for Structural Training capture preparation."""

from ml_training.structural.src.prepare_runtime_captures import *  # noqa: F401,F403
from ml_training.structural.src.prepare_runtime_captures import main


if __name__ == "__main__":
    main()

from __future__ import annotations

import torch

from ml_training.structural.src.train_local import (
    _cpu_byte_rng_state,
    _restore_rng_state,
    _rng_state,
)


def test_sampler_rng_state_is_normalised_to_cpu_byte_tensor() -> None:
    source = torch.Generator().manual_seed(20260902)
    deserialised = source.get_state().to(dtype=torch.int16)

    restored = _cpu_byte_rng_state(deserialised)

    assert restored.device.type == "cpu"
    assert restored.dtype == torch.uint8
    target = torch.Generator()
    target.set_state(restored)
    assert torch.equal(target.get_state(), source.get_state())


def test_global_rng_restore_accepts_non_byte_deserialised_tensor() -> None:
    state = _rng_state()
    expected = state["torch"].clone()
    state["torch"] = state["torch"].to(dtype=torch.int16)

    _restore_rng_state(state)

    assert torch.equal(torch.get_rng_state(), expected)

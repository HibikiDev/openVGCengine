


from __future__ import annotations

import torch


def amp(dev: torch.device) -> torch.autocast:

    return torch.autocast(dev.type, dtype=torch.float16, enabled=dev.type == "cuda")


def grad_scaler(dev: torch.device) -> torch.amp.GradScaler:

    return torch.amp.GradScaler(dev.type, enabled=dev.type == "cuda")


def pick_device(name: str | None = None) -> torch.device:


    if name:
        return torch.device(name)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if getattr(torch, "xpu", None) is not None and torch.xpu.is_available():
        return torch.device("xpu")
    if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def free_memory() -> None:

    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    if getattr(torch, "xpu", None) is not None and torch.xpu.is_available():
        torch.xpu.empty_cache()
    if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        torch.mps.empty_cache()


def device_arg(name: str) -> torch.device:

    dev = torch.device(name)
    if dev.type == "cuda" and not torch.cuda.is_available():
        raise SystemExit("--device cuda: no CUDA device (use --device cpu for a CPU smoke run)")
    return dev

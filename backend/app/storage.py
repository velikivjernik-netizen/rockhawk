from pathlib import Path

from app.config import get_settings


def storage_root() -> Path:
    root = Path(get_settings().storage_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_bytes(relative_path: str, data: bytes) -> Path:
    path = storage_root() / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def read_bytes(relative_path: str) -> bytes:
    return (storage_root() / relative_path).read_bytes()

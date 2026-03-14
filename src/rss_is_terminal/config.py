"""Configuration management with XDG directory conventions."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from platformdirs import user_config_dir, user_data_dir

APP_NAME = "rss_is_terminal"


def config_dir() -> Path:
    path = Path(user_config_dir(APP_NAME))
    path.mkdir(parents=True, exist_ok=True)
    return path


def data_dir() -> Path:
    path = Path(user_data_dir(APP_NAME))
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return data_dir() / "rss.db"


def config_path() -> Path:
    return config_dir() / "config.toml"


@dataclass
class AppConfig:
    refresh_interval_minutes: int = 30
    default_browser_cmd: str | None = None
    vim_mode: bool = True
    max_articles_per_feed: int = 200
    fetch_timeout_seconds: int = 30
    concurrent_fetches: int = 10

    @classmethod
    def load(cls) -> AppConfig:
        path = config_path()
        if not path.exists():
            cfg = cls()
            cfg.save()
            return cfg
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def save(self) -> None:
        path = config_path()
        lines = []
        for name, f in self.__dataclass_fields__.items():
            val = getattr(self, name)
            if val is None:
                lines.append(f"# {name} =")
            elif isinstance(val, bool):
                lines.append(f"{name} = {'true' if val else 'false'}")
            elif isinstance(val, int):
                lines.append(f"{name} = {val}")
            elif isinstance(val, str):
                lines.append(f'{name} = "{val}"')
        path.write_text("\n".join(lines) + "\n")

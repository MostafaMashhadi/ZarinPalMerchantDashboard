from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_env_file() -> None:
    """Load repo-root .env file if environment variables are not already set."""
    backend_dir = Path(__file__).resolve().parent.parent
    root_env = backend_dir.parent / ".env"
    local_env = backend_dir / ".env"
    env_path = root_env if root_env.exists() else (local_env if local_env.exists() else None)
    if not env_path:
        return

    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip("'\"")
            if k not in os.environ:
                os.environ[k] = v


load_env_file()


@dataclass(frozen=True)
class ClickHouseConfig:
    host: str = os.getenv("CLICKHOUSE_HOST", "localhost")
    http_port: int = int(os.getenv("CLICKHOUSE_HTTP_PORT", "8123"))
    native_port: int = int(os.getenv("CLICKHOUSE_NATIVE_PORT", "9000"))
    database: str = os.getenv("CLICKHOUSE_DB", "zarinpal")
    user: str = os.getenv("CLICKHOUSE_USER", "zarinpal")
    password: str = os.getenv("CLICKHOUSE_PASSWORD", "zarinpal")

    @property
    def http_url(self) -> str:
        return f"http://{self.host}:{self.http_port}"


@dataclass(frozen=True)
class PostgresConfig:
    host: str = os.getenv("POSTGRES_HOST", "localhost")
    port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    database: str = os.getenv("POSTGRES_DB", "zarinpal")
    user: str = os.getenv("POSTGRES_USER", "zarinpal")
    password: str = os.getenv("POSTGRES_PASSWORD", "zarinpal")

    @property
    def dsn(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


@dataclass(frozen=True)
class RedisConfig:
    host: str = os.getenv("REDIS_HOST", "localhost")
    port: int = int(os.getenv("REDIS_PORT", "6379"))
    password: str = os.getenv("REDIS_PASSWORD", "zarinpal")


default_clickhouse_config = ClickHouseConfig()
default_postgres_config = PostgresConfig()
default_redis_config = RedisConfig()

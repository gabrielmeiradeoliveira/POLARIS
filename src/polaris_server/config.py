import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ServerConfig:
    pg_dsn: str = os.environ.get(
        "POLARIS_PG_DSN",
        "postgresql://polaris:polaris_local_dev@127.0.0.1:5432/polaris_poc",
    )
    max_body_bytes: int = 5 * 1024 * 1024

    def __post_init__(self) -> None:
        if not self.pg_dsn or not self.pg_dsn.strip():
            raise ValueError("pg_dsn não pode ser vazio.")
        if self.max_body_bytes <= 0:
            raise ValueError("max_body_bytes deve ser positivo.")

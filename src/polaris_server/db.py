from pathlib import Path
import psycopg
from polaris_server.config import ServerConfig

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def get_connection(config: ServerConfig | None = None) -> psycopg.Connection:
    cfg = config or ServerConfig()
    return psycopg.connect(cfg.pg_dsn)


def run_migrations(config: ServerConfig | None = None) -> list[str]:
    applied: list[str] = []
    with get_connection(config) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW());"
            )
            for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
                version = sql_file.stem
                cur.execute("SELECT 1 FROM schema_migrations WHERE version = %s;", (version,))
                if cur.fetchone():
                    continue
                cur.execute(sql_file.read_text(encoding="utf-8"))
                cur.execute("INSERT INTO schema_migrations (version) VALUES (%s);", (version,))
                applied.append(version)
        conn.commit()
    return applied


def init_schema(config: ServerConfig | None = None) -> None:
    run_migrations(config)
    try:
        from polaris_server.triage import backfill_missing_fingerprints
        backfill_missing_fingerprints()
    except Exception:
        pass

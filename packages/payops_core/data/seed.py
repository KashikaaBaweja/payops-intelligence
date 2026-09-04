from pathlib import Path

from payops_core.data.db import apply_schema, make_engine
from payops_core.data.synthetic_generator import generate


def seed(database_url: str | None = None) -> dict:
    engine = make_engine(database_url)
    if engine.url.drivername.startswith("sqlite") and engine.url.database:
        Path(engine.url.database).parent.mkdir(parents=True, exist_ok=True)
    apply_schema(engine)
    stats = generate(engine)
    return stats


def main() -> None:
    stats = seed()
    print(f"Seeded {stats['payments']} payments and {len(stats['incidents'])} planted incidents.")


if __name__ == "__main__":
    main()

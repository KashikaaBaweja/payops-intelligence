from __future__ import annotations

from typing import Any

from payops_core.data.engine import create_schema, make_engine, session_factory
from payops_core.data.synthetic_generator import generate


def seed(database_url: str | None = None, rng_seed: int = 42) -> dict[str, Any]:
    engine = make_engine(database_url)
    create_schema(engine)
    factory = session_factory(engine)
    with factory() as session:
        stats = generate(session, seed=rng_seed)
        session.commit()
    return stats


def main() -> None:
    stats = seed()
    print(
        f"Seeded {stats['payments']} payments across {stats['merchants']} merchants "
        f"and {len(stats['incidents'])} planted incidents."
    )


if __name__ == "__main__":
    main()

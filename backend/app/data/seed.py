"""Seed entry point.

By default builds the deterministic mock dataset and ingests it into an
in-memory repository, printing a summary (works anywhere, no DB needed).

In production this is where you would target the PostgisRepository instead;
the ingestion logic is identical because both satisfy the Repository interface.
"""
from __future__ import annotations

from app.data.ingest import ingest
from app.data.mock import generate
from app.repositories.memory import InMemoryRepository


def build_seeded_repo(seed: int = 42, **kwargs) -> tuple[InMemoryRepository, object]:
    repo = InMemoryRepository()
    dataset = generate(seed=seed, **kwargs)
    report = ingest(dataset, repo)
    return repo, report


def main() -> int:
    repo, report = build_seeded_repo()
    print("Seed complete (in-memory):")
    print(f"  planning areas : {len(repo.planning_areas())}")
    print(f"  mrt stations   : {len(repo.mrt_stations())}")
    print(f"  bus stops      : {len(repo.bus_stops())}")
    print(f"  schools        : {len(repo.schools())}")
    print(f"  blocks loaded  : {report.blocks_loaded}")
    print(f"  with area FK   : {report.blocks_with_planning_area}")
    print(f"  transactions   : {report.transactions_loaded}")
    print(f"  proximity rows : {report.proximity_rows}")
    print(f"  rejected blocks: {report.blocks_rejected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

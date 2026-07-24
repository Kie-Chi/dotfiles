"""Normalized software registry search records."""

from dataclasses import asdict, dataclass


@dataclass
class SearchResult:
    source: str
    ecosystem: str
    name: str
    kind: str
    version: str | None = None
    description: str = ""
    ref: str | None = None
    homepage: str | None = None
    publisher: str | None = None
    managed_group: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class ProviderReport:
    source: str
    results: list[SearchResult]
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "results": [result.to_dict() for result in self.results],
            "error": self.error,
        }

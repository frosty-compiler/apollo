import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any, Mapping, Iterator


@dataclass
class Reference:
    """A single reference item from `url_to_info`."""

    url: str
    description: str
    snippets: List[str]
    title: str
    meta: Mapping[str, Any] = field(default_factory=dict)
    citation_uuid: int = -1

    def __repr__(self) -> str:
        query = self.meta.get("query")
        return (
            f"Reference(id={self.citation_uuid}, "
            f"title={self.title!r}, "
            f"query={query!r}), "
            f"url={self.url!r}"
        )

    def as_text(self) -> str:
        """Return a plain-text dump."""
        snip = "\n".join(self.snippets)
        return f"{snip}"

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Reference":
        """Factory used by `ReferenceLibrary`."""
        return cls(
            url=payload["url"],
            description=payload["description"],
            snippets=payload["snippets"],
            title=payload["title"],
            meta=payload.get("meta", {}),
            citation_uuid=int(payload.get("citation_uuid", -1)),
        )


class ReferenceLibrary:
    """
    Loads `url_to_info_polished.json` once and exposes:
        - lib[id]: Reference  (mapping-like access)
        - lib.get(id): Reference | None
        - len(lib): number of refs
        - iteration: yields (id, Reference) pairs
    """

    def __init__(self, json_path: str | Path):
        self.json_path = Path(json_path).expanduser().resolve()
        self._id2ref: Dict[int, Reference] = {}
        self._url2id: Dict[str, int] = {}

        self._load()

    def __getitem__(self, ref_id: int) -> Reference:
        return self._id2ref[ref_id]

    def get(self, ref_id: int, default: Optional[Any] = None) -> Optional[Reference]:
        return self._id2ref.get(ref_id, default)

    def __len__(self) -> int:
        return len(self._id2ref)

    def __iter__(self) -> Iterator[tuple[int, Reference]]:
        yield from self._id2ref.items()

    def url_for(self, ref_id: int) -> str:
        return self._id2ref[ref_id].url

    def id_for_url(self, url: str) -> int:
        return self._url2id[url]

    def _load(self) -> None:
        raw = json.loads(self.json_path.read_text(encoding="utf-8"))
        self._url2id = raw["url_to_unified_index"]

        url2ref_obj: Dict[str, Reference] = {
            url: Reference.from_dict(info) for url, info in raw["url_to_info"].items()
        }
        self._id2ref = {}
        for url, idx in self._url2id.items():
            ref = url2ref_obj[url]
            ref.citation_uuid = idx
            self._id2ref[idx] = ref


if __name__ == "__main__":
    lib = ReferenceLibrary(
        ".../output/apollo/gen_articles/SciWiki-100/SocialSciences/1/Feudalism/gen_articles_v0/url_to_info_polished.json"
    )
    print(f"{len(lib)} references loaded\n")

    r3 = lib[3]
    print(r3)
    print(r3.as_text())

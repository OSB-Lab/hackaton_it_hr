import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Generic, TypeVar

from app.modules.catalog.schemas import Blueprint, Catalog, Manifest
from app.modules.catalog.validators import validate_blueprint

DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "catalog"
T = TypeVar("T")


def _no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def decode(model, raw):
    json.loads(raw, object_pairs_hook=_no_duplicate_keys)
    return model.model_validate_json(raw)


@dataclass(frozen=True)
class Loaded(Generic[T]):
    document: T
    checksum: str


class CatalogRepository:
    def __init__(self, root: Path = DATA_ROOT):
        self.root = root.resolve()
        self.manifest = decode(Manifest, (self.root / "manifest.json").read_bytes())

    def _load(self, key: str, kind: str, model):
        ref = next((r for r in self.manifest.artifacts if r.key == key and r.kind == kind), None)
        if ref is None:
            raise ValueError("Unknown artifact version")
        path = (self.root / ref.path).resolve()
        if Path(ref.path).is_absolute() or not path.is_relative_to(self.root):
            raise ValueError("Artifact path escapes catalog root")
        raw = path.read_bytes()
        checksum = hashlib.sha256(raw).hexdigest()
        if checksum != ref.sha256:
            raise ValueError("Artifact checksum mismatch")
        document = decode(model, raw)
        if (document.id, document.version) != (ref.id, ref.version):
            raise ValueError("Artifact identity mismatch")
        return Loaded(document, checksum)

    def catalog(self, version: str | None = None) -> Loaded[Catalog]:
        if version is None:
            key = self.manifest.activeCatalog
        else:
            matches = [r for r in self.manifest.artifacts if r.kind == "catalog" and r.version == version]
            if len(matches) != 1:
                raise ValueError("Unknown or ambiguous catalog version")
            key = matches[0].key
        return self._load(key, "catalog", Catalog)

    def blueprint(self, key: str) -> Loaded[Blueprint]:
        loaded = self._load(key, "blueprint", Blueprint)
        catalog = self.catalog(loaded.document.catalogVersion).document
        validate_blueprint(catalog, loaded.document)
        return loaded

    def validate_all(self):
        for ref in self.manifest.artifacts:
            if ref.kind == "catalog":
                self._load(ref.key, "catalog", Catalog)
            else:
                self.blueprint(ref.key)
        active = [self.blueprint(key).document for key in self.manifest.activeBlueprints]
        pairs = [(b.specialization, b.grade) for b in active]
        if len(pairs) != len(set(pairs)):
            raise ValueError("Multiple active versions for specialization/grade")
        if any(b.catalogVersion != self.catalog().document.version for b in active):
            raise ValueError("Active blueprint catalog mismatch")

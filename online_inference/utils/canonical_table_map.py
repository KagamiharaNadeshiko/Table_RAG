import os
import json
import re
from typing import Dict, List, Optional, Set, Tuple


def _slugify(name: str) -> str:
    """
    Create a readable, stable canonical id from a filename or table name.
    - Lowercase
    - Preserve CJK characters so that names like "华为_2024财报" remain distinct
    - Replace other non-alphanumeric/CJK characters with underscore
    - Collapse consecutive underscores
    - Trim leading/trailing underscores
    """
    lowered = name.lower()
    # Keep 0-9, a-z, A-Z, and common CJK range \u4e00-\u9fa5
    replaced = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fa5]+", "_", lowered)
    collapsed = re.sub(r"_+", "_", replaced)
    return collapsed.strip("_")


class CanonicalTableIndex:
    """
    Build a canonical table id mapping and alias set from schema (.json) and excel (.xlsx/.csv) files.
    """
    def __init__(self, schema_dir: str, excel_dir: str) -> None:
        self.schema_dir = schema_dir
        self.excel_dir = excel_dir
        self.canonical_to_aliases: Dict[str, Set[str]] = {}
        self.alias_to_canonical: Dict[str, str] = {}
        self.canonical_to_files: Dict[str, Dict[str, Optional[str]]] = {}
        self._build_index()

    def _add_alias(self, canonical_id: str, alias: str) -> None:
        if not alias:
            return
        if canonical_id not in self.canonical_to_aliases:
            self.canonical_to_aliases[canonical_id] = set()
        self.canonical_to_aliases[canonical_id].add(alias)
        self.alias_to_canonical[alias] = canonical_id

    def _register_file(self, canonical_id: str, json_file: Optional[str] = None, excel_file: Optional[str] = None) -> None:
        entry = self.canonical_to_files.get(canonical_id, {"json": None, "excel": None})
        if json_file:
            entry["json"] = json_file
        if excel_file:
            entry["excel"] = excel_file
        self.canonical_to_files[canonical_id] = entry

    def _build_index(self) -> None:
        # Scan excel files
        if os.path.isdir(self.excel_dir):
            for file in os.listdir(self.excel_dir):
                if not file.lower().endswith((".xlsx", ".csv")):
                    continue
                stem = os.path.splitext(file)[0]
                canonical_id = _slugify(stem)
                self._add_alias(canonical_id, stem)
                self._add_alias(canonical_id, file)
                self._register_file(canonical_id, excel_file=file)

        # Scan schema JSON files
        if os.path.isdir(self.schema_dir):
            for file in os.listdir(self.schema_dir):
                if not file.lower().endswith(".json"):
                    continue
                stem = os.path.splitext(file)[0]
                canonical_id = _slugify(stem)
                json_path = os.path.join(self.schema_dir, file)
                # Load JSON and consider internal table_name as alias as well
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    internal_name = data.get("table_name")
                except Exception:
                    internal_name = None

                # Prefer internal_name for canonical if present
                if internal_name:
                    preferred = _slugify(internal_name)
                    # Merge any prior aliases under old canonical into preferred
                    if preferred != canonical_id and canonical_id in self.canonical_to_aliases:
                        # Remap existing aliases to the preferred id
                        for alias in self.canonical_to_aliases.get(canonical_id, set()):
                            self.alias_to_canonical[alias] = preferred
                        existing = self.canonical_to_aliases.pop(canonical_id)
                        for alias in existing:
                            self._add_alias(preferred, alias)
                        # Move file registration
                        if canonical_id in self.canonical_to_files:
                            files = self.canonical_to_files.pop(canonical_id)
                            self.canonical_to_files[preferred] = files
                    canonical_id = preferred

                self._add_alias(canonical_id, stem)
                self._add_alias(canonical_id, file)
                if internal_name:
                    self._add_alias(canonical_id, internal_name)
                self._register_file(canonical_id, json_file=file)

    def get_canonical_id(self, any_name: str) -> Optional[str]:
        """Return canonical id for any known alias or filename stem."""
        if not any_name:
            return None
        # Exact alias match first
        if any_name in self.alias_to_canonical:
            return self.alias_to_canonical[any_name]
        # Try stem without extension
        stem = os.path.splitext(any_name)[0]
        if stem in self.alias_to_canonical:
            return self.alias_to_canonical[stem]
        # Try slugified
        slug = _slugify(stem)
        if slug in self.canonical_to_aliases:
            return slug
        return None

    def get_aliases(self, canonical_id: str) -> List[str]:
        return sorted(list(self.canonical_to_aliases.get(canonical_id, set())))

    def get_preferred_excel_file(self, canonical_id: str) -> Optional[str]:
        entry = self.canonical_to_files.get(canonical_id)
        if not entry:
            return None
        return entry.get("excel")

    def get_preferred_json_file(self, canonical_id: str) -> Optional[str]:
        entry = self.canonical_to_files.get(canonical_id)
        if not entry:
            return None
        return entry.get("json")

    def best_service_aliases(self, canonical_id: str) -> List[str]:
        """
        Provide a compact set of aliases to send to the SQL service to maximize match probability.
        Priority: excel stem, json stem, internal name (already included in aliases), canonical id.
        """
        aliases = []
        excel = self.get_preferred_excel_file(canonical_id)
        json_file = self.get_preferred_json_file(canonical_id)
        if excel:
            aliases.append(os.path.splitext(excel)[0])
        if json_file:
            aliases.append(os.path.splitext(json_file)[0])
        # Add canonical id for visibility
        aliases.append(canonical_id)
        # Deduplicate while preserving order
        seen = set()
        result = []
        for a in aliases:
            if a and a not in seen:
                result.append(a)
                seen.add(a)
        return result

    def list_canonical_ids(self) -> List[str]:
        return sorted(list(self.canonical_to_aliases.keys()))



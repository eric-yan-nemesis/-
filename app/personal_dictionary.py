"""Offline Octanove levels plus original Wordset definitions and usage examples."""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re

DICTIONARY_PATH = Path(__file__).resolve().parents[1] / 'data' / 'lexiscope_dictionary.json'


def spelling_variants(word: str) -> list[str]:
    """Explicit source alternatives only; no guessed synonyms or senses."""
    return list(dict.fromkeys(' '.join(part.lower().split()) for part in word.split('/') if part.strip()))


@lru_cache(maxsize=1)
def load_personal_dictionary() -> dict:
    data = DICTIONARY_PATH.read_bytes()
    checksum_path = DICTIONARY_PATH.with_suffix('.sha256')
    expected = checksum_path.read_text(encoding='ascii').split()[0]
    if not re.fullmatch('[0-9a-f]{64}', expected) or hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError('个人词典校验失败，请重新构建或恢复发布版本。')
    result = json.loads(data)
    if result.get('schema_version') != 1 or not isinstance(result.get('entries'), list):
        raise RuntimeError('个人词典格式不受支持。')
    return result


@lru_cache(maxsize=1)
def _entry_index() -> dict:
    index = {}
    for entry in load_personal_dictionary()['entries']:
        index[entry['word'].lower()] = entry
        for variant in spelling_variants(entry['word']):
            index.setdefault(variant, entry)
    return index


def dictionary_info() -> dict:
    data = load_personal_dictionary()
    return deepcopy({key: data[key] for key in ('schema_version', 'name', 'coverage', 'sources')})


def lookup_entry(word: str) -> dict | None:
    entry = _entry_index().get(' '.join(word.lower().strip().split()))
    return deepcopy(entry) if entry else None


def annotation_fields(lemma: str, candidates: list[dict]) -> dict:
    entry = lookup_entry(lemma)
    senses = entry['senses'] if entry else []
    source_pos = {candidate['pos'] for candidate in candidates}
    matching = [sense for sense in senses if sense['pos'] in source_pos]
    # A definition and its usage must belong to the same source sense. Choosing
    # the first definition and first example independently mixes meanings.
    selected = next((sense for sense in matching if sense['examples']), matching[0] if matching else None)
    definition = selected['definition'] if selected else ''
    example = selected['examples'][0] if selected and selected['examples'] else ''
    source = deepcopy(load_personal_dictionary()['sources']['wordset'])
    return {
        'dictionary_senses': senses,
        'definition': definition,
        'example': example,
        'definition_source': source if definition else None,
        'example_source': source if example else None,
        'annotation_source': 'wordset' if definition or example else 'none',
        'selected_sense_id': selected['id'] if selected else None,
    }

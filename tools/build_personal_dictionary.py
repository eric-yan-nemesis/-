#!/usr/bin/env python3
"""Rebuild the local Octanove × Wordset subset from pinned upstream sources.

Only source headwords and their explicit slash-separated spellings are joined.
Source examples may be phrases; no examples or translations are generated.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path, PurePosixPath
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PROFILE_COMMIT = 'd4e45b75b38f27b30dfc5c44d8c571aec7e7092f'
PROFILE_NAME = 'octanove-vocabulary-profile-c1c2-1.0.csv'
PROFILE_SHA256 = '18c33a407f2f89f7b8de9671c6d45fe3ea0bce45e7d2d7dcaab48d73e0f7b380'
WORDSET_COMMIT = '4503bfafbe4556361a296b9d368c18168dfb56c3'
WORDSET_URL = f'https://github.com/wordset/wordset-dictionary/archive/{WORDSET_COMMIT}.zip'
WORDSET_SHA256 = '59f47028b505832aae5c8d1c8ae9663a3c037888bf470104e97dafa7064db129'
MAX_DOWNLOAD = 100 * 1024 * 1024
MAX_EXPANDED = 250 * 1024 * 1024


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def download_archive(path: Path) -> None:
    if path.exists():
        if sha256(path) != WORDSET_SHA256:
            raise ValueError('已有 Wordset 归档校验失败；请先自行备份或换一个缓存目录。')
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.wordset-', delete=False) as stream:
            temporary = Path(stream.name)
            request = urllib.request.Request(WORDSET_URL, headers={'User-Agent': 'LexiScope-Dictionary-Builder/1.0'})
            with urllib.request.urlopen(request, timeout=45) as response:
                size = 0
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_DOWNLOAD:
                        raise ValueError('Wordset 下载超过 100 MiB 限制。')
                    stream.write(chunk)
        if sha256(temporary) != WORDSET_SHA256:
            raise ValueError('Wordset 下载校验失败，不能用于构建。')
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def read_wordset(path: Path) -> tuple[dict, dict]:
    if path.stat().st_size > MAX_DOWNLOAD or sha256(path) != WORDSET_SHA256:
        raise ValueError('Wordset 归档不是所需的固定版本或校验失败。')
    data = {}
    notices = {}
    prefix = f'wordset-dictionary-{WORDSET_COMMIT}/'
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) > 1000 or sum(item.file_size for item in members) > MAX_EXPANDED:
            raise ValueError('Wordset 归档展开大小或成员数超过安全限制。')
        for item in members:
            member_path = PurePosixPath(item.filename)
            if (member_path.is_absolute() or '..' in member_path.parts or '\\' in item.filename
                    or item.flag_bits & 1 or not item.filename.startswith(prefix)):
                raise ValueError('Wordset 归档包含不安全的路径或加密内容。')
            relative = item.filename[len(prefix):]
            if relative in ('LICENSE', 'Readme.md'):
                notices[relative] = archive.read(item)
            elif relative.startswith('data/') and relative.endswith('.json'):
                entries = json.loads(archive.read(item))
                if not isinstance(entries, dict):
                    raise ValueError('Wordset JSON 结构无效。')
                for word, entry in entries.items():
                    key = word.casefold()
                    data.setdefault(key, []).append(entry)
    if set(notices) != {'LICENSE', 'Readme.md'} or not data:
        raise ValueError('Wordset 归档缺少数据或原始许可说明。')
    return data, notices


def build(profile: Path, archive: Path) -> tuple[dict, dict]:
    if sha256(profile) != PROFILE_SHA256:
        raise ValueError('Octanove 原始词表校验失败。')
    wordset, notices = read_wordset(archive)
    records = {}
    seen = set()
    raw_count = 0
    with profile.open(encoding='utf-8-sig', newline='') as handle:
        for row in csv.DictReader(handle):
            raw_count += 1
            word, pos, level, note = (row[key].strip() for key in ('headword', 'pos', 'CEFR', 'notes'))
            if level not in ('C1', 'C2'):
                raise ValueError('Octanove 中存在非 C1/C2 等级。')
            key = (word, pos, level, note)
            if key in seen:
                continue
            seen.add(key)
            records.setdefault(word, []).append({'level': level, 'pos': pos, 'notes': note, 'source': 'octanove'})

    entries = []
    matched_forms = set()
    duplicate_senses = 0
    for word in sorted(records, key=lambda value: (value.casefold(), value)):
        # This is spelling expansion, never stemming or a synonym replacement.
        forms = list(dict.fromkeys(part.strip().casefold() for part in word.split('/') if part.strip()))
        senses = []
        sense_keys = set()
        for form in forms:
            lexical_entries = wordset.get(form, [])
            if not lexical_entries:
                continue
            matched_forms.add(form)
            for lexical_entry in lexical_entries:
                for meaning in lexical_entry.get('meanings', []):
                    definition = meaning.get('def', '')
                    if not isinstance(definition, str) or not definition.strip():
                        continue
                    example = meaning.get('example')
                    examples = [example] if isinstance(example, str) and example.strip() else []
                    sense = {
                        'id': meaning.get('id', ''),
                        'definition': definition,
                        'pos': meaning.get('speech_part', ''),
                        'examples': list(dict.fromkeys(examples)),
                        'source': 'wordset',
                        'wordset_word': lexical_entry.get('word', form),
                    }
                    key = (sense['wordset_word'], sense['id'], definition, sense['pos'], tuple(sense['examples']))
                    if key not in sense_keys:
                        senses.append(sense)
                        sense_keys.add(key)
                    else:
                        duplicate_senses += 1
        entries.append({'word': word, 'cefr': records[word], 'senses': senses})

    coverage = {
        'octanove_raw_records': raw_count,
        'octanove_distinct_records': len(seen),
        'headwords': len(entries),
        'wordset_total_headwords': sum(len(items) for items in wordset.values()),
        'wordset_casefolded_headwords': len(wordset),
        'matched_wordset_headwords': sum(bool(entry['senses']) for entry in entries),
        'matched_spelling_forms': len(matched_forms),
        'headwords_with_examples': sum(any(sense['examples'] for sense in entry['senses']) for entry in entries),
        'headwords_without_examples': sum(not any(sense['examples'] for sense in entry['senses']) for entry in entries),
        'senses': sum(len(entry['senses']) for entry in entries),
        'senses_with_examples': sum(bool(sense['examples']) for entry in entries for sense in entry['senses']),
        'examples': sum(len(sense['examples']) for entry in entries for sense in entry['senses']),
        'duplicate_spelling_senses_removed': duplicate_senses,
        'records_by_level': {level: sum(record['level'] == level for entry in entries for record in entry['cefr']) for level in ('C1', 'C2')},
        'unmatched_headwords': [entry['word'] for entry in entries if not entry['senses']],
    }
    result = {
        'schema_version': 1,
        'name': 'LexiScope · Octanove × Wordset',
        'license': 'CC BY-SA 4.0; preserve the underlying Princeton WordNet 3.0 license',
        'sources': {
            'octanove': {
                'name': 'Octanove Vocabulary Profile C1/C2 v1.0',
                'url': f'https://github.com/openlanguageprofiles/olp-en-cefrj/blob/{PROFILE_COMMIT}/{PROFILE_NAME}',
                'commit': PROFILE_COMMIT,
                'license': 'CC BY-SA 4.0',
                'license_url': 'https://creativecommons.org/licenses/by-sa/4.0/',
                'creator': 'Octanove Labs / Open Language Profiles',
                'sha256': PROFILE_SHA256,
            },
            'wordset': {
                'name': 'Wordset Dictionary',
                'url': f'https://github.com/wordset/wordset-dictionary/tree/{WORDSET_COMMIT}',
                'commit': WORDSET_COMMIT,
                'license': 'CC BY-SA 4.0; underlying Princeton WordNet 3.0 license retained',
                'license_url': 'https://creativecommons.org/licenses/by-sa/4.0/',
                'creator': 'Wordset, Inc. and contributors; underlying WordNet © 2006 Princeton University',
                'archive_url': WORDSET_URL,
                'archive_sha256': WORDSET_SHA256,
            },
        },
        'notices': {
            'wordset': notices['LICENSE'].decode('utf-8'),
        },
        'coverage': coverage,
        'modifications': [
            'Exact duplicate Octanove rows removed; original source POS, level and sense notes retained.',
            'Joined by case-insensitive headword and explicit slash-separated source spellings only.',
            'Selected corresponding Wordset definitions and examples; original strings and source sense IDs retained.',
            'Only completely identical Wordset spelling/sense/definition/POS/example records deduplicated; spelling provenance retained.',
            'No source sense-to-CEFR mapping inferred; no translations or examples generated.',
        ],
        'warnings': [
            'CEFR levels describe Octanove word/POS records, not individually verified Wordset senses or passage occurrences.',
            'Wordset examples may be phrases rather than complete sentences; missing examples remain empty.',
            'No Chinese translations are supplied by these two sources.',
        ],
        'entries': entries,
    }
    return result, notices


def main() -> None:
    parser = argparse.ArgumentParser(description='用固定版本 Octanove 和 Wordset 构建本地个人词典。')
    parser.add_argument('--wordset-archive', type=Path, help='使用已下载的固定版本 Wordset ZIP')
    parser.add_argument('--cache-dir', type=Path, default=ROOT / 'dictionaries-local' / 'wordset-source')
    parser.add_argument('--profile', type=Path, default=ROOT / 'data' / PROFILE_NAME)
    parser.add_argument('--output', type=Path, default=ROOT / 'data' / 'lexiscope_dictionary.json')
    parser.add_argument('--license-dir', type=Path, default=ROOT / 'data' / 'wordset')
    args = parser.parse_args()
    archive = args.wordset_archive
    if archive is None:
        archive = args.cache_dir / f'wordset-{WORDSET_COMMIT}.zip'
        download_archive(archive)
    result, notices = build(args.profile, archive)
    payload = (json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    args.output.with_suffix('.sha256').write_text(hashlib.sha256(payload).hexdigest() + '\n', encoding='ascii')
    args.license_dir.mkdir(parents=True, exist_ok=True)
    (args.license_dir / 'LICENSE').write_bytes(notices['LICENSE'])
    (args.license_dir / 'README.md').write_bytes(notices['Readme.md'])
    marker = 'WordNet Release 3.0'
    license_text = notices['LICENSE'].decode('utf-8')
    if marker not in license_text:
        raise ValueError('原始许可中缺少 Princeton WordNet 许可。')
    (args.license_dir / 'PRINCETON_WORDNET_LICENSE.txt').write_text(license_text[license_text.index(marker):], encoding='utf-8')
    print('已构建：', args.output)
    print('JSON SHA256：', hashlib.sha256(payload).hexdigest())
    print(json.dumps(result['coverage'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, zipfile.BadZipFile, KeyError, json.JSONDecodeError) as error:
        raise SystemExit('构建失败：' + str(error))

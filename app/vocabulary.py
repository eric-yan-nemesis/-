"""Source-backed lexical candidates; source levels are never sense verification."""
from __future__ import annotations

import csv
import hashlib
import re
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from lemminflect import getAllInflections

DATA = Path(__file__).resolve().parents[1] / 'data'
SOURCE_URL = 'https://github.com/openlanguageprofiles/olp-en-cefrj/blob/d4e45b75b38f27b30dfc5c44d8c571aec7e7092f/octanove-vocabulary-profile-c1c2-1.0.csv'
SOURCE = {'name': 'Octanove Vocabulary Profile C1/C2 v1.0', 'url': SOURCE_URL,
          'license': 'CC BY-SA 4.0', 'creator': 'Octanove Labs / Open Language Profiles',
          'license_url': 'https://creativecommons.org/licenses/by-sa/4.0/'}
EXPECTED_SHA256 = '18c33a407f2f89f7b8de9671c6d45fe3ea0bce45e7d2d7dcaab48d73e0f7b380'
TOKEN = re.compile(r"[A-Za-z]+(?:['’\-][A-Za-z]+)*")
POS = {'noun': 'NOUN', 'verb': 'VERB', 'adjective': 'ADJ', 'adverb': 'ADV'}

# Original annotations, not copied dictionary definitions. The level comes ONLY
# from the bundled source. Multiple senses require contextual review.
ANNOTATIONS = {
 'complexity': ('复杂性；复杂程度', 'The state of having many connected parts.', 'The complexity of the problem surprised us.'),
 'concur': ('同意；意见一致', 'To express the same opinion as someone else.', 'The two reviewers concurred with the findings.'),
 'avid': ('热衷的；渴望的', 'Very interested in an activity or subject.', 'She is an avid reader of history.'),
 'alleviate': ('缓解；减轻', 'To make a difficulty or discomfort less severe.', 'The policy may alleviate financial pressure.'),
 'elaborate': ('精心设计的；详述（视词性而定）', 'Detailed and carefully developed; as a verb, to explain further.', 'Please elaborate on your proposal.'),
 'scrutiny': ('仔细审查', 'Close and careful examination of something.', 'The proposal came under public scrutiny.'),
 'plausible': ('看似合理的；可信的', 'Seeming reasonable enough to be possible.', 'The researcher offered a plausible explanation.'),
 'inherent': ('固有的；内在的', 'Existing as a natural part of something.', 'Every approach has inherent limitations.'),
 'candid': ('坦率的；直言不讳的', 'Expressing thoughts openly and honestly.', 'We had a candid discussion about the risks.'),
 'detrimental': ('有害的；不利的', 'Causing damage or an undesirable effect.', 'The delay was detrimental to the project.'),
 'resilient': ('有韧性的；能恢复的', 'Able to recover after stress or difficulty.', 'Resilient communities recover after a crisis.'),
 'pervasive': ('普遍存在的；遍布的', 'Present throughout many parts of a place or situation.', 'The influence of technology is pervasive.'),
 'ephemeral': ('短暂的；转瞬即逝的', 'Existing for only a short time.', 'Online fame can be ephemeral.'),
 'meticulous': ('一丝不苟的；细致的', 'Giving careful attention to small details.', 'She kept meticulous records of every experiment.'),
 'profound': ('深刻的；深远的', 'Having a deep or powerful effect or meaning.', 'The discovery had a profound influence on science.'),
 'cloak': ('斗篷；掩饰（须核对语境和词性）', 'A loose outer garment; figuratively, something that hides.', 'He wore a cloak in the cold.'),
 'timid': ('胆怯的；羞怯的', 'Lacking confidence when facing others or taking action.', 'The timid child gradually joined the conversation.'),
}


@lru_cache(maxsize=1)
def lexicon():
    path = DATA / 'octanove-vocabulary-profile-c1c2-1.0.csv'
    if hashlib.sha256(path.read_bytes()).hexdigest() != EXPECTED_SHA256:
        raise RuntimeError('词表校验失败，请从固定版本恢复原始数据。')
    by_form = defaultdict(list)
    seen = set()
    entries = []
    with path.open(encoding='utf-8-sig', newline='') as handle:
        for row in csv.DictReader(handle):
            lemma, pos, level, notes = (row[k].strip() for k in ('headword', 'pos', 'CEFR', 'notes'))
            key = (lemma.lower(), pos, level, notes)
            if key in seen or level not in ('C1', 'C2'):
                continue
            seen.add(key)
            entry = {'lemma': lemma, 'pos': pos or 'unknown', 'level': level, 'notes': notes}
            entries.append(entry)
            forms = {lemma.lower()}
            # Restrict morphology by source POS; derivations are not inflections.
            if pos in POS:
                parts = lemma.split(' ')
                # Inflect the lexical verb in a phrasal verb, or the final noun
                # in an ordinary noun phrase. Preserve the other words exactly.
                head = 0 if pos == 'verb' else len(parts) - 1
                if len(parts) == 1 or pos in ('verb', 'noun'):
                    for inflections in getAllInflections(parts[head], upos=POS[pos]).values():
                        for form in inflections:
                            variant = parts.copy()
                            variant[head] = form.lower()
                            forms.add(' '.join(variant).lower())
            for form in forms:
                by_form[form].append(entry)
    return dict(by_form), entries


def sentence_at(text: str, start: int, end: int) -> str:
    left = max(text.rfind('.', 0, start), text.rfind('!', 0, start), text.rfind('?', 0, start), text.rfind('\n', 0, start)) + 1
    match = re.search(r'[.!?\n]', text[end:])
    right = end + match.start() + 1 if match else len(text)
    return text[left:right].strip()[:1200]


def analyze_text(text: str) -> dict:
    by_form, _ = lexicon()
    tokens = list(TOKEN.finditer(text))
    groups = {}
    occurrences = []
    index = 0
    while index < len(tokens):
        candidates, span_end, consumed = [], tokens[index].end(), 1
        # Longest phrase first, with whitespace only between its words.
        for size in range(min(6, len(tokens) - index), 0, -1):
            subset = tokens[index:index + size]
            if any(not text[a.end():b.start()].isspace() for a, b in zip(subset, subset[1:])):
                continue
            form = ' '.join(t.group().replace('’', "'").lower() for t in subset)
            if form in by_form:
                candidates, span_end, consumed = by_form[form], subset[-1].end(), size
                break
        if candidates:
            # Every competing POS/sense/level is disclosed; never silently pick
            # a high level and present it as contextually verified.
            unique = {(x['lemma'], x['pos'], x['level'], x['notes']) for x in candidates}
            chosen = min(candidates, key=lambda x: (x['level'], x['lemma'], x['pos']))
            lemma = chosen['lemma']
            group_key = lemma.lower()
            if group_key not in groups:
                chinese, definition, example = ANNOTATIONS.get(lemma.lower(), (
                    '需结合上下文确认中文释义（可启用 AI）',
                    'No offline sense definition is available; contextual review is required.',
                    sentence_at(text, tokens[index].start(), span_end)))
                notes = '词表支持词条等级；当前语境的词性与义项尚未核实。'
                details = sorted({f"{x['pos']} · {x['level']}" + (f" · {x['notes']}" if x['notes'] else '') for x in candidates})
                notes += ' 来源记录：' + '; '.join(details)
                if len(unique) > 1:
                    notes += ' 存在多种词性、等级或义项候选。'
                groups[group_key] = {
                    'id': f'v{len(groups) + 1}', 'lemma': lemma,
                    'level': chosen['level'], 'pos': ' / '.join(sorted({x['pos'] for x in candidates})),
                    'chinese': chinese, 'definition': definition, 'example': example,
                    'status': 'reference', 'source': dict(SOURCE), 'notes': notes,
                    'count': 0, 'forms': [], 'context_verified': False,
                    'level_candidates': sorted({x['level'] for x in candidates}),
                    'source_candidates': [dict(x) for x in candidates],
                }
            item = groups[group_key]
            existing = {(x['lemma'], x['pos'], x['level'], x['notes']) for x in item['source_candidates']}
            added = [x for x in candidates if (x['lemma'], x['pos'], x['level'], x['notes']) not in existing]
            if added:
                item['source_candidates'].extend(dict(x) for x in added)
                item['level_candidates'] = sorted({x['level'] for x in item['source_candidates']})
                item['level'] = item['level_candidates'][0]
                item['pos'] = ' / '.join(sorted({x['pos'] for x in item['source_candidates']}))
                item['notes'] += ' 其他出现位置的来源候选：' + '; '.join(
                    f"{x['pos']} · {x['level']}" + (f" · {x['notes']}" if x['notes'] else '') for x in added)
            start = tokens[index].start()
            surface = text[start:span_end]
            item['count'] += 1
            if surface not in item['forms'] and len(item['forms']) < 1000:
                item['forms'].append(surface)
            occurrences.append({'start': start, 'end': span_end, 'item_id': item['id'],
                                'surface': surface, 'context': sentence_at(text, start, span_end), 'uncertain': True})
        index += consumed
    return {'text': text, 'items': list(groups.values()), 'occurrences': occurrences,
            'warnings': [
                '等级来自 Octanove 开放词表，非官方认证；词性、义项和语境仍需核对。词表覆盖有限，未标记的词不代表低于 C1。',
                '离线中文释义和例句是通用学习注释，尚非针对每次出现的上下文释义。'], 'ai_used': False}

"""Behavior checks against the bundled, attributed reference profile."""
import csv
import hashlib

import pytest

from app.vocabulary import DATA, EXPECTED_SHA256, analyze_text


def items_by_lemma(result):
    return {item['lemma']: item for item in result['items']}


def test_reference_integrity_and_exact_source_samples():
    path = DATA / 'octanove-vocabulary-profile-c1c2-1.0.csv'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == EXPECTED_SHA256
    with path.open(newline='', encoding='utf-8-sig') as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2136
    assert len({row['headword'] for row in rows}) == 1955
    result = items_by_lemma(analyze_text('Meticulous pervasive complexity concur alleviate resilient.'))
    for lemma, level, pos in [('meticulous', 'C2', 'adjective'), ('pervasive', 'C2', 'adjective'),
                              ('complexity', 'C1', 'noun'), ('concur', 'C1', 'verb'),
                              ('alleviate', 'C1', 'verb'), ('resilient', 'C1', 'adjective')]:
        assert any(row['headword'] == lemma and row['CEFR'] == level and row['pos'] == pos for row in rows)
        assert result[lemma]['level'] == level
        assert result[lemma]['status'] == 'reference'
        assert result[lemma]['source']['license'] == 'CC BY-SA 4.0'
        assert EXPECTED_SHA256 not in result[lemma]['source']['url']
        assert 'd4e45b75b38f27b30dfc5c44d8c571aec7e7092f' in result[lemma]['source']['url']


def test_absent_terms_are_not_invented_as_advanced():
    result = analyze_text('assess substantial ambiguous facilitate ubiquitous nuance')
    assert not result['items']
    assert any('未标记' in warning for warning in result['warnings'])


@pytest.mark.parametrize(('text', 'lemma', 'forms'), [
    ('alleviated alleviates alleviating alleviate', 'alleviate', ['alleviated', 'alleviates', 'alleviating', 'alleviate']),
    ('concurred concur concurring concurs', 'concur', ['concurred', 'concur', 'concurring', 'concurs']),
    ('complexities complexity complexity', 'complexity', ['complexities', 'complexity']),
])
def test_inflections_group_and_repetitions_count(text, lemma, forms):
    result = analyze_text(text)
    assert len(result['items']) == 1
    item = result['items'][0]
    assert item['lemma'] == lemma
    assert item['count'] == len(text.split())
    assert item['forms'] == forms
    assert len(result['occurrences']) == item['count']


def test_no_substring_or_derivational_matching():
    assert not analyze_text('meticulousness uncomplexity concurredx')['items']


def test_codepoint_offsets_preserve_emoji_and_original_case():
    text = '📚 中文 Meticulous!\nA CANDID report.'
    result = analyze_text(text)
    assert result['text'] == text
    for occurrence in result['occurrences']:
        assert text[occurrence['start']:occurrence['end']] == occurrence['surface']
    meticulous = next(o for o in result['occurrences'] if o['surface'] == 'Meticulous')
    assert meticulous['start'] == text.index('Meticulous')


def test_known_phrase_is_one_longest_match_and_not_across_punctuation():
    result = analyze_text('A bona fide offer. A bona, fide offer.')
    phrase = next(item for item in result['items'] if item['lemma'] == 'bona fide')
    assert phrase['count'] == 1
    occurrence = next(o for o in result['occurrences'] if o['item_id'] == phrase['id'])
    assert occurrence['surface'] == 'bona fide'


def test_inflected_phrasal_verbs_are_grouped_with_base_phrase():
    result = analyze_text('We mull over this plan. Yesterday we mulled over it.')
    phrase = next(item for item in result['items'] if item['lemma'] == 'mull over')
    assert phrase['count'] == 2
    assert phrase['forms'] == ['mull over', 'mulled over']


def test_polysemous_cast_keeps_source_sense_notes_and_uncertainty():
    result = analyze_text('They cast a shadow. She wore a plaster cast.')
    cast = next(item for item in result['items'] if item['lemma'] == 'cast')
    assert cast['count'] == 2
    assert 'plaster cast, mold' in cast['notes']
    assert 'hire actors' in cast['notes']
    assert 'noun' in cast['pos'] and 'verb' in cast['pos']
    assert cast['context_verified'] is False
    assert all(o['uncertain'] for o in result['occurrences'] if o['item_id'] == cast['id'])

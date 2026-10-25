"""Behavior checks for the attributed Octanove × Wordset personal dictionary."""
import csv
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import Analysis, app
from app.vocabulary import analyze_text


ROOT = Path(__file__).resolve().parents[1]


def dictionary():
    from app.personal_dictionary import load_personal_dictionary
    return load_personal_dictionary()


def entry(word):
    from app.personal_dictionary import lookup_entry
    return lookup_entry(word)


def analyzed_item(text, lemma):
    return next(item for item in analyze_text(text)['items'] if item['lemma'] == lemma)


def test_personal_dictionary_preserves_every_distinct_octanove_record():
    data = dictionary()
    assert data['schema_version'] == 1
    assert len(data['entries']) == 1955
    with (ROOT / 'data' / 'octanove-vocabulary-profile-c1c2-1.0.csv').open(
            encoding='utf-8-sig', newline='') as handle:
        # Outer padding in two source headwords is normalized by the builder;
        # preserve their lexical identity, POS, level and sense notes.
        expected = {tuple(row[key].strip() for key in ('headword', 'pos', 'CEFR', 'notes'))
                    for row in csv.DictReader(handle)}
    actual = {(item['word'], record['pos'], record['level'], record['notes'])
              for item in data['entries'] for record in item['cefr']}
    assert len(expected) == 2108
    assert actual == expected
    assert all(record['source'] == 'octanove'
               for item in data['entries'] for record in item['cefr'])
    assert all('level' not in sense and 'cefr' not in sense
               for item in data['entries'] for sense in item['senses'])


def test_source_licenses_and_pinned_revisions_travel_with_dictionary():
    sources = dictionary()['sources']
    assert sources['octanove']['license'] == 'CC BY-SA 4.0'
    assert 'CC BY-SA 4.0' in sources['wordset']['license']
    assert 'Princeton WordNet' in sources['wordset']['license']
    assert sources['octanove']['commit'] == 'd4e45b75b38f27b30dfc5c44d8c571aec7e7092f'
    assert sources['wordset']['commit'] == '4503bfafbe4556361a296b9d368c18168dfb56c3'
    assert 'creativecommons.org/licenses/by-sa/4.0' in sources['wordset']['license_url']
    assert dictionary()['notices']['wordset'] == (ROOT / 'data' / 'wordset' / 'LICENSE').read_text()
    assert 'PRINCETON UNIVERSITY MAKES NO REPRESENTATIONS OR WARRANTIES' in dictionary()['notices']['wordset']


def test_real_meticulous_entry_keeps_original_wordset_phrases_and_sense_ids():
    value = entry('meticulous')
    assert value['cefr'] == [dict(level='C2', pos='adjective', notes='', source='octanove')]
    senses = {sense['id']: sense for sense in value['senses']}
    assert senses['233ff48563']['definition'] == 'marked by precise accordance with details'
    assert senses['233ff48563']['examples'] == ['meticulous research']
    assert senses['2d4f94fbf9']['definition'] == 'marked by extreme care in treatment of details'
    assert senses['2d4f94fbf9']['examples'] == ['a meticulous craftsman']
    assert all(sense['source'] == 'wordset' for sense in senses.values())
    assert all(sense['wordset_word'] == 'meticulous' for sense in senses.values())


def test_source_only_scope_does_not_assign_advanced_levels_to_wordset_basic_words():
    # Wordset has maintain and mitigate, but Octanove C1/C2 does not.
    assert entry('maintain') is None
    assert entry('mitigate') is None
    assert not analyze_text('We maintain the plan and mitigate risk.')['items']


def test_lookup_normalizes_case_and_outer_spaces_without_guessing_new_lemmas():
    assert entry(' Meticulous ') == entry('meticulous')
    assert entry('invented_dictionary_word_92835') is None


def test_missing_wordset_examples_stay_empty_in_analysis():
    value = entry('mountaineer')
    assert value['senses']
    assert all(not sense['examples'] for sense in value['senses'])
    item = analyzed_item('A mountaineer climbed the mountain.', 'mountaineer')
    assert item['example'] == ''
    assert item['example_source'] is None
    assert item['dictionary_senses']
    assert all(not sense['examples'] for sense in item['dictionary_senses'])
    assert item['definition_source']['name'] == 'Wordset Dictionary'


def test_analysis_uses_wordset_instead_of_old_authored_examples():
    item = analyzed_item('Meticulous research revealed the answer.', 'meticulous')
    assert item['example'] in {'meticulous research', 'a meticulous craftsman'}
    assert item['example_source']['name'] == 'Wordset Dictionary'
    assert item['definition_source']['name'] == 'Wordset Dictionary'
    assert item['annotation_source'] == 'wordset'
    assert item['source']['name'] != item['example_source']['name']
    assert item['context_verified'] is False
    assert {example for sense in item['dictionary_senses'] for example in sense['examples']} == {
        'meticulous research', 'a meticulous craftsman'}


def test_summary_definition_and_example_belong_to_the_same_wordset_sense():
    # Agency's first four noun senses lack examples, while its fifth has one.
    # A summary must not attach that fifth-sense example to the first definition.
    item = analyzed_item('The agency issued a report.', 'agency')
    assert item['example']
    assert any(sense['definition'] == item['definition'] and item['example'] in sense['examples']
               for sense in item['dictionary_senses'])


def test_inflected_spelling_variants_keep_one_original_cefr_entry():
    item = analyzed_item('She scrutinised the report and scrutinized the draft.', 'scrutinize/scrutinise')
    assert item['level'] == 'C1'
    assert item['count'] == 2
    assert item['forms'] == ['scrutinised', 'scrutinized']
    assert item['dictionary_senses']
    assert all(sense['source'] == 'wordset' for sense in item['dictionary_senses'])


def test_export_validation_preserves_dictionary_provenance_and_original_examples():
    result = analyze_text('Meticulous research. A mountaineer climbed.')
    validated = Analysis.model_validate(result).model_dump()
    for original, saved in zip(result['items'], validated['items']):
        for key in ('dictionary_senses', 'example_source', 'definition_source', 'annotation_source'):
            assert saved[key] == original[key]


@pytest.fixture
def client():
    with TestClient(app) as value:
        yield value


def test_personal_dictionary_api_is_offline_and_download_is_complete(client, monkeypatch):
    import urllib.request
    import httpx
    monkeypatch.delenv('AI_API_KEY', raising=False)
    monkeypatch.setattr(urllib.request, 'urlopen', lambda *a, **kw: (_ for _ in ()).throw(
        AssertionError('dictionary lookup must not make a network request')))
    monkeypatch.setattr(httpx, 'AsyncClient', lambda *a, **kw: (_ for _ in ()).throw(
        AssertionError('dictionary lookup must not call a model')))
    summary = client.get('/api/dictionary')
    assert summary.status_code == 200
    assert summary.json()['sources'] == dictionary()['sources']
    assert summary.json()['coverage'] == dictionary()['coverage']
    found = client.get('/api/dictionary/lookup', params={'word': 'meticulous'})
    assert found.status_code == 200
    assert found.json() == entry('meticulous')
    missing = client.get('/api/dictionary/lookup', params={'word': 'unknown_dictionary_word_92835'})
    assert missing.status_code == 404
    downloaded = client.get('/api/dictionary/download')
    assert downloaded.status_code == 200
    assert 'attachment;' in downloaded.headers['content-disposition']
    assert 'json' in downloaded.headers['content-type']
    assert downloaded.json() == dictionary()


def test_dictionary_lookup_does_not_interpret_word_as_a_file_path(client):
    response = client.get('/api/dictionary/lookup', params={'word': '../../.env'})
    assert response.status_code in {404, 422}
    assert 'Traceback' not in response.text

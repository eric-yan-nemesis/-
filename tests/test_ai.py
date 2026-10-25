"""Mocked provider checks; these do not claim live model validation."""
import asyncio
import json

import httpx
import pytest

from app import ai
from app.vocabulary import analyze_text


def annotation(index=0, chinese='细致的', **overrides):
    value = dict(index=index, chinese=chinese, definition='Careful about details.',
                 example='A meticulous review revealed an error.', pos='adjective',
                 matches_reference_sense=True)
    value.update(overrides)
    return value


def estimate(quote='ubiquitous', lemma='ubiquitous', level='C2'):
    return dict(quote=quote, lemma=lemma, level=level, pos='adjective',
                chinese='普遍存在的', definition='Present in many places.',
                example='Computers are ubiquitous.')


def test_no_api_key_returns_offline_without_network(monkeypatch):
    monkeypatch.delenv('AI_API_KEY', raising=False)
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: (_ for _ in ()).throw(AssertionError('network forbidden')))
    result = asyncio.run(ai.enrich(analyze_text('Meticulous notes.'), True))
    assert result['ai_used'] is False
    assert any('未配置' in message for message in result['warnings'])


def test_reference_level_cannot_be_overridden_by_model():
    original = analyze_text('Meticulous notes.')
    data = {'annotations': [annotation(level='C1', status='estimate')], 'estimates': []}
    result = ai.apply_annotations(original, data, True)
    assert result['items'][0]['level'] == 'C2'
    assert result['items'][0]['status'] == 'reference'
    assert result['items'][0]['chinese'] == '细致的'
    assert result['items'][0]['context_verified'] is False
    assert result['occurrences'][0]['uncertain'] is True
    assert original['items'][0]['chinese'] != '细致的'


def test_two_senses_get_distinct_rows_and_correct_occurrences():
    original = analyze_text('They cast an actor. She wore a plaster cast.')
    indices = [i for i, o in enumerate(original['occurrences']) if o['surface'] == 'cast']
    data = {'annotations': [annotation(indices[0], '选派演员'), annotation(indices[1], '石膏模具')], 'estimates': []}
    result = ai.apply_annotations(original, data, False)
    cast = [item for item in result['items'] if item['lemma'] == 'cast']
    assert len(cast) == 2
    assert {item['chinese'] for item in cast} == {'选派演员', '石膏模具'}
    assert all(item['count'] == 1 for item in cast)
    cast_occurrences = [o for o in result['occurrences'] if o['surface'] == 'cast']
    assert len({o['item_id'] for o in cast_occurrences}) == 2


def test_model_sense_mismatch_is_disclosed():
    value = annotation()
    value['matches_reference_sense'] = False
    result = ai.apply_annotations(analyze_text('Meticulous notes.'), {'annotations': [value]}, False)
    assert '可能不符合' in result['items'][0]['notes']


def test_estimates_have_no_fabricated_source_and_repeat_count():
    result = ai.apply_annotations(analyze_text('ubiquitous and ubiquitous'), {'estimates': [estimate()]}, True)
    assert len(result['items']) == 1
    item = result['items'][0]
    assert item['status'] == 'estimate' and item['source'] is None
    assert item['count'] == 2
    assert all(o['uncertain'] for o in result['occurrences'])
    assert '估计' in item['notes']


def test_disabling_estimates_and_known_lower_levels_suppresses_additions():
    assert ai.apply_annotations(analyze_text('ubiquitous'), {'estimates': [estimate()]}, False)['items'] == []
    result = ai.apply_annotations(analyze_text('assess'), {'estimates': [estimate('assess', 'assess')]}, True)
    assert result['items'] == []


def test_bad_estimate_spans_and_overlaps_are_rejected():
    result = ai.apply_annotations(analyze_text('Meticulous notes.'), {
        'estimates': [estimate('missing'), estimate('Meticulous', 'meticulous'), estimate('.*', 'injection')],
    }, True)
    assert len(result['items']) == 1
    assert len(result['occurrences']) == 1


def test_live_request_shape_with_mocked_provider_and_no_secret_leak(monkeypatch):
    monkeypatch.setenv('AI_API_KEY', 'test-secret-never-log')
    monkeypatch.setenv('AI_BASE_URL', 'https://example.test/v1')
    calls = []
    class Client:
        def __init__(self, **kwargs):
            assert kwargs['follow_redirects'] is False
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def post(self, url, headers, json):
            calls.append((url, headers, json))
            request = httpx.Request('POST', url)
            return httpx.Response(200, request=request, json={'choices': [{'message': {'content':
                __import__('json').dumps({'annotations': [annotation()], 'estimates': []})}}]})
    monkeypatch.setattr(httpx, 'AsyncClient', Client)
    result = asyncio.run(ai.enrich(analyze_text('Meticulous notes.'), False))
    assert result['ai_used'] is True
    assert len(calls) == 1
    assert calls[0][0] == 'https://example.test/v1/chat/completions'
    assert calls[0][1]['Authorization'] == 'Bearer test-secret-never-log'
    assert json.loads(calls[0][2]['messages'][1]['content'])['allow_estimates'] is False
    assert 'test-secret-never-log' not in json.dumps(result)


def test_provider_error_is_safe_and_preserves_offline_result(monkeypatch):
    monkeypatch.setenv('AI_API_KEY', 'test-secret-never-log')
    class Client:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def post(self, *args, **kwargs):
            raise httpx.ConnectError('private provider body test-secret-never-log')
    monkeypatch.setattr(httpx, 'AsyncClient', Client)
    result = asyncio.run(ai.enrich(analyze_text('Meticulous notes.'), True))
    assert result['ai_used'] is False
    assert result['items'][0]['level'] == 'C2'
    assert 'test-secret-never-log' not in json.dumps(result)
    assert any('请求失败' in warning for warning in result['warnings'])


@pytest.mark.parametrize('data', [
    {'annotations': None, 'estimates': None},
    {'annotations': 'invalid-list', 'estimates': {}},
    {'annotations': [None, [], 7, {'index': True}, {'index': -1}], 'estimates': [None, [], 5]},
    {'annotations': [{'index': 999, 'chinese': 'x'}], 'estimates': [{'quote': 'x', 'lemma': ['invalid'], 'level': 'C2'}]},
])
def test_adversarial_provider_field_types_preserve_safe_source_result(data):
    result = ai.apply_annotations(analyze_text('Meticulous notes.'), data, True)
    assert len(result['items']) == 1
    assert result['items'][0]['lemma'] == 'meticulous'
    assert result['items'][0]['level'] == 'C2'
    assert result['items'][0]['status'] == 'reference'
    assert result['ai_used'] is False


def test_ai_size_limit_is_checked_before_network(monkeypatch):
    monkeypatch.setenv('AI_API_KEY', 'test-secret-never-log')
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: (_ for _ in ()).throw(AssertionError('network forbidden')))
    result = asyncio.run(ai.enrich(analyze_text('x' * 16001), True))
    assert result['ai_used'] is False
    assert any('16,000' in warning for warning in result['warnings'])


def test_malformed_provider_base_url_falls_back_without_network(monkeypatch):
    monkeypatch.setenv('AI_API_KEY', 'test-secret-never-log')
    monkeypatch.setenv('AI_BASE_URL', 'https://[broken')
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: (_ for _ in ()).throw(AssertionError('network forbidden')))
    result = asyncio.run(ai.enrich(analyze_text('Meticulous notes.'), False))
    assert result['ai_used'] is False
    assert any('格式无效' in warning for warning in result['warnings'])


def test_model_annotation_controls_are_cleaned_before_docx_export():
    from app.exports import build_docx
    from app.main import Analysis
    from docx import Document
    import io
    value = annotation(chinese='细致\x00\x0b\ud800\uffff的')
    result = ai.apply_annotations(analyze_text('Meticulous notes.'), {'annotations': [value]}, False)
    assert result['items'][0]['chinese'] == '细致的'
    Analysis.model_validate(result)
    document = Document(io.BytesIO(build_docx(result)))
    assert any('细致的' in cell.text for row in document.tables[0].rows for cell in row.cells)


@pytest.mark.parametrize(('text', 'quote', 'lemma'), [
    ('assess', 'assess', ' ASSESS '),
    ('assessed', 'assessed', 'assess'),
    ('ubiquitous', 'ubiquitous', 'unrelated'),
])
def test_estimate_normalization_blocks_lower_lemmas_and_unrelated_claims(text, quote, lemma):
    result = ai.apply_annotations(analyze_text(text), {'estimates': [estimate(quote, lemma)]}, True)
    assert result['items'] == []


def test_estimate_lemma_is_normalized_and_real_inflection_can_match():
    result = ai.apply_annotations(analyze_text('ubiquitous'), {'estimates': [estimate(lemma=' ubiquitous ')]}, True)
    assert result['items'][0]['lemma'] == 'ubiquitous'
    assert result['items'][0]['status'] == 'estimate'


@pytest.mark.parametrize('text', [
    'A legal brief arrived. They briefed the team.',
    'They briefed the team. A legal brief arrived.',
])
def test_source_pos_selects_correct_brief_level_for_each_context(text):
    original = analyze_text(text)
    annotations = []
    for index, occurrence in enumerate(original['occurrences']):
        if occurrence['surface'] == 'brief':
            annotations.append(dict(index=index, chinese='诉讼摘要', pos='noun',
                definition='A document presenting a legal argument.', example='The lawyer filed a brief.',
                matches_reference_sense=True))
        elif occurrence['surface'] == 'briefed':
            annotations.append(dict(index=index, chinese='简要告知', pos='verb',
                definition='To give important information before an activity.', example='She briefed the team.',
                matches_reference_sense=True))
    result = ai.apply_annotations(original, {'annotations': annotations}, False)
    brief = {item['pos']: item for item in result['items'] if item['lemma'] == 'brief'}
    assert set(brief) == {'noun', 'verb'}
    assert brief['noun']['level'] == 'C2'
    assert brief['verb']['level'] == 'C1'
    assert brief['noun']['status'] == brief['verb']['status'] == 'reference'
    assert brief['noun']['count'] == brief['verb']['count'] == 1
    assert all(source['pos'] == 'noun' for source in brief['noun']['source_candidates'])


def test_cast_matching_and_mismatching_senses_do_not_merge():
    original = analyze_text('She wore a cast. The tree cast a shadow.')
    cast_indices = [i for i, occurrence in enumerate(original['occurrences']) if occurrence['surface'] == 'cast']
    annotations = []
    for index, matches in zip(cast_indices, [True, False]):
        annotations.append(dict(index=index, chinese='投射或塑形', pos='verb', definition='To cast something.',
            example='They cast it.', matches_reference_sense=matches))
    result = ai.apply_annotations(original, {'annotations': annotations}, True)
    cast = [item for item in result['items'] if item['lemma'] == 'cast']
    assert len(cast) == 2
    assert {item['status'] for item in cast} == {'reference', 'estimate'}
    assert all(item['count'] == 1 for item in cast)
    uncertain = next(item for item in cast if item['status'] == 'estimate')
    assert '本次等级适用性未确定' in uncertain['notes']


def test_same_chinese_label_with_different_english_senses_does_not_merge():
    original = analyze_text('They cast it. Then they cast it again.')
    annotations = [annotation(0, '投射', definition='To select performers.'),
                   annotation(1, '投射', definition='To suggest doubt.')]
    for value in annotations:
        value['pos'] = 'verb'
    result = ai.apply_annotations(original, {'annotations': annotations}, False)
    cast = [item for item in result['items'] if item['lemma'] == 'cast']
    assert len(cast) == 2
    assert {item['definition'] for item in cast} == {'To select performers.', 'To suggest doubt.'}

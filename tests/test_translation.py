import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.translation import split_material


@pytest.mark.parametrize('text', ['A paragraph.\n\nAnother paragraph. ' * 500, 'x' * 100000, '😀 English 中文 ' * 1000])
def test_chunks_preserve_all_original_text_and_bound_each_request(text):
    chunks = split_material(text)
    assert ''.join(chunks) == text
    assert all(0 < len(chunk) <= 4000 for chunk in chunks)


def test_no_key_is_explicit_failure_not_fake_translation(monkeypatch):
    monkeypatch.delenv('AI_API_KEY', raising=False)
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: pytest.fail('must not contact a provider'))
    with TestClient(app) as client:
        response = client.post('/api/translate', json={'text': 'Meticulous research.'})
    assert response.status_code == 503
    assert 'AI_API_KEY' in response.json()['detail']
    assert 'translation' not in response.json()


@pytest.mark.parametrize('text', ['', '   ', 'x' * 100001, '\ud800', 'a\x00b'])
def test_translation_validation_does_not_echo_private_material(text):
    with TestClient(app) as client:
        response = client.post('/api/translate', content=json.dumps({'text': text}, ensure_ascii=True), headers={'Content-Type': 'application/json'})
    assert response.status_code == 422
    assert response.json() == {'detail': '输入格式无效，请检查文本长度、字符和分析结果。'}


def mock_provider(monkeypatch, mode='success'):
    calls = []
    monkeypatch.setenv('AI_API_KEY', 'test-translation-secret')
    monkeypatch.setenv('AI_BASE_URL', 'https://example.test/v1')

    class Client:
        def __init__(self, **kwargs):
            assert kwargs['follow_redirects'] is False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, headers, json):
            calls.append((url, headers, json))
            if mode == 'failure':
                raise httpx.ConnectError('provider private body test-translation-secret')
            content = {'translation': '这是第 ' + str(len(calls)) + ' 段译文。'}
            if mode == 'invalid':
                content = {'translation': []}
            return httpx.Response(200, request=httpx.Request('POST', url), json={'choices': [{
                'finish_reason': 'length' if mode == 'truncated' else 'stop',
                'message': {'content': __import__('json').dumps(content)}}]})

    monkeypatch.setattr(httpx, 'AsyncClient', Client)
    return calls


def test_long_material_translates_each_segment_in_order_without_changing_source(monkeypatch):
    calls = mock_provider(monkeypatch)
    text = 'Meticulous research supports resilient communities.\n\n' * 200
    with TestClient(app) as client:
        response = client.post('/api/translate', json={'text': text})
    assert response.status_code == 200
    payload = response.json()
    assert len(calls) > 1
    assert ''.join(call[2]['messages'][1]['content'] for call in calls) == text
    assert payload['translation'] == '\n\n'.join('这是第 ' + str(i) + ' 段译文。' for i in range(1, len(calls) + 1))
    assert payload['segments'] == len(calls)
    assert payload['target_language'] == 'zh-CN'
    assert 'test-translation-secret' not in json.dumps(payload)
    assert all(call[1]['Authorization'] == 'Bearer test-translation-secret' for call in calls)


@pytest.mark.parametrize('mode', ['failure', 'invalid', 'truncated'])
def test_provider_failures_are_safe_and_never_claim_complete_translation(monkeypatch, mode):
    mock_provider(monkeypatch, mode)
    with TestClient(app) as client:
        response = client.post('/api/translate', json={'text': 'A private passage.'})
    assert response.status_code == 502
    assert 'translation' not in response.json()
    assert 'test-translation-secret' not in response.text
    assert 'private passage' not in response.text


@pytest.mark.parametrize('url', ['http://example.test/v1', 'https://[broken', 'https://example.test:bad/v1', 'https://u:p@example.test/v1', 'https://example.test/v1?key=secret'])
def test_invalid_configuration_does_not_make_a_provider_request(monkeypatch, url):
    monkeypatch.setenv('AI_API_KEY', 'test-translation-secret')
    monkeypatch.setenv('AI_BASE_URL', url)
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: pytest.fail('invalid URL must not be used'))
    with TestClient(app) as client:
        response = client.post('/api/translate', json={'text': 'Test material.'})
    assert response.status_code == 503


def test_disconnect_stops_before_transmitting_text(monkeypatch):
    from app.translation import TranslationFailure, translate_material
    calls = mock_provider(monkeypatch)

    async def disconnected():
        return True

    with pytest.raises(TranslationFailure, match='取消'):
        asyncio.run(translate_material('Private material.', disconnected))
    assert not calls

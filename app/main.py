from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from starlette.concurrency import run_in_threadpool

from app import ai
from app.vocabulary import analyze_text, lexicon

ROOT = Path(__file__).resolve().parents[1]
MAX_BODY = 11 * 1024 * 1024
app = FastAPI(title='词境 · LexiScope', version='1.0.0')


@app.exception_handler(RequestValidationError)
async def validation_error(request, error):
    # Never echo uploaded text or invalid Unicode through validation messages.
    return JSONResponse({'detail': '输入格式无效，请检查文本长度、字符和分析结果。'}, status_code=422)


def valid_xml_string(value: str) -> bool:
    return all(c in '\n\r\t' or 32 <= ord(c) <= 0xD7FF or
               0xE000 <= ord(c) <= 0xFFFD or 0x10000 <= ord(c) <= 0x10FFFF for c in value)


class BodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] not in ('POST', 'PUT', 'PATCH'):
            return await self.app(scope, receive, send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            chunk = message.get('body', b'')
            size += len(chunk)
            if size > MAX_BODY:
                return await JSONResponse({'detail': '请求过大，文件最大 10 MiB。'}, status_code=413)(scope, receive, send)
            chunks.append(chunk)
            if not message.get('more_body'):
                break
        sent = False

        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {'type': 'http.request', 'body': b''.join(chunks), 'more_body': False}
            return await receive()
        await self.app(scope, replay, send)


app.add_middleware(BodyLimit)


@app.middleware('http')
async def security_headers(request, call_next):
    origin = request.headers.get('origin')
    if request.method == 'POST' and origin:
        from urllib.parse import urlsplit
        if urlsplit(origin).netloc != request.headers.get('host'):
            return JSONResponse({'detail': '禁止跨站请求。'}, status_code=403)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
    response.headers['Cache-Control'] = 'no-store'
    return response


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str = Field(min_length=1, max_length=100000)
    use_ai: bool = False
    include_estimates: bool = True

    @model_validator(mode='after')
    def nonblank(self):
        if not self.text.strip():
            raise ValueError('请输入英文文本。')
        if not valid_xml_string(self.text):
            raise ValueError('文本包含不支持的控制字符。')
        return self


class VocabularyItem(BaseModel):
    id: str = Field(max_length=100)
    lemma: str = Field(max_length=200)
    level: Literal['C1', 'C2']
    pos: str = Field(max_length=1200)
    chinese: str = Field(max_length=2000)
    definition: str = Field(max_length=2000)
    example: str = Field(max_length=2000)
    status: Literal['reference', 'estimate']
    source: dict | None = None
    notes: str = Field(default='', max_length=10000)
    count: int = Field(ge=0, le=50000)
    forms: list[str] = Field(default_factory=list, max_length=1000)
    context_verified: bool = False
    level_candidates: list[str] = Field(default_factory=list)
    source_candidates: list[dict] = Field(default_factory=list, max_length=100)

    @field_validator('lemma', 'pos', 'chinese', 'definition', 'example', 'notes')
    @classmethod
    def valid_xml_text(cls, value):
        if not valid_xml_string(value):
            raise ValueError('词汇字段包含不支持的字符。')
        return value


class Occurrence(BaseModel):
    start: int = Field(ge=0)
    end: int = Field(ge=1)
    item_id: str = Field(max_length=100)
    surface: str = Field(max_length=200)
    context: str = Field(default='', max_length=2000)
    uncertain: bool = True


class Analysis(BaseModel):
    text: str = Field(min_length=1, max_length=100000)
    items: list[VocabularyItem] = Field(max_length=3000)
    occurrences: list[Occurrence] = Field(max_length=50000)
    warnings: list[str] = Field(default_factory=list, max_length=100)
    ai_used: bool = False

    @model_validator(mode='after')
    def valid_spans(self):
        if not valid_xml_string(self.text):
            raise ValueError('文本包含不支持的控制字符。')
        ids = {item.id for item in self.items}
        if len(ids) != len(self.items):
            raise ValueError('词汇 ID 重复。')
        end = 0
        for occurrence in self.occurrences:
            if (occurrence.start < end or occurrence.end <= occurrence.start or
                occurrence.end > len(self.text) or occurrence.item_id not in ids or
                self.text[occurrence.start:occurrence.end] != occurrence.surface):
                raise ValueError('无效的高亮范围。')
            end = occurrence.end
        return self


class ExportRequest(BaseModel):
    analysis: Analysis


@app.get('/api/health')
def health():
    _, entries = lexicon()
    return {'status': 'ok', 'ai_configured': ai.configured(),
            'ocr_available': bool(shutil.which('tesseract')), 'reference_entries': len(entries)}


@app.post('/api/analyze')
async def analyze(request: AnalyzeRequest):
    result = await run_in_threadpool(analyze_text, request.text)
    if request.use_ai:
        result = await ai.enrich(result, request.include_estimates)
    return result


@app.post('/api/documents')
async def document(file: UploadFile = File(...), ocr: bool = Form(False)):
    from app.documents import extract_document
    try:
        content = await file.read(10 * 1024 * 1024 + 1)
        return await run_in_threadpool(extract_document, file.filename or '', content, ocr)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from None
    finally:
        await file.close()


@app.post('/api/export/{format}')
async def export(format: Literal['docx', 'pdf', 'csv'], request: ExportRequest):
    from app.exports import build_csv, build_docx, build_pdf
    builders = {'docx': (build_docx, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
                'pdf': (build_pdf, 'application/pdf'), 'csv': (build_csv, 'text/csv; charset=utf-8')}
    builder, media_type = builders[format]
    try:
        content = await run_in_threadpool(builder, request.analysis.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from None
    return Response(content, media_type=media_type,
                    headers={'Content-Disposition': f'attachment; filename="lexiscope-annotated.{format}"'})


if (ROOT / 'static').is_dir():
    app.mount('/', StaticFiles(directory=ROOT / 'static', html=True), name='static')

import csv
import io

from docx import Document
import fitz

from app.main import Analysis
from app.personal_dictionary import lookup_entry, load_personal_dictionary
from app.vocabulary import analyze_text
from app.exports import build_docx, build_pdf, build_csv


def test_wordset_synonyms_stay_with_their_original_sense():
    senses = {sense['id']: sense for sense in lookup_entry('alleviate')['senses']}
    physical = senses['9d70f76524']
    other = senses['b28b420250']
    assert physical['definition'] == 'to provide physical relief, as from pain'
    assert physical['synonyms'] == ['relieve']
    assert other['definition'] == 'to make easier'
    assert other['synonyms'] == ['ease']
    assert all('level' not in sense and 'cefr' not in sense for sense in senses.values())


def test_synonyms_are_selected_from_same_sense_as_definition_and_example():
    result = analyze_text('The meticulous researchers alleviate stress.')
    for item in result['items']:
        selected = next(s for s in item['dictionary_senses'] if s['id'] == item['selected_sense_id'])
        assert item['synonyms'] == selected['synonyms']
        assert item['definition'] == selected['definition']
    assert next(i for i in result['items'] if i['lemma'] == 'meticulous')['synonyms'] == ['punctilious']
    assert next(i for i in result['items'] if i['lemma'] == 'alleviate')['level'] == 'C1'


def test_missing_source_synonyms_are_empty_and_not_fabricated():
    sense = next(s for s in lookup_entry('meticulous')['senses'] if s['id'] == '2d4f94fbf9')
    assert sense['synonyms'] == []
    data = load_personal_dictionary()
    assert data['coverage']['headwords_with_synonyms'] == sum(any(s['synonyms'] for s in e['senses']) for e in data['entries'])
    for entry in data['entries']:
        for sense in entry['senses']:
            assert sense['source'] == 'wordset'
            assert all(word.strip() and word.lower() != sense['wordset_word'].lower() for word in sense['synonyms'])


def test_synonyms_survive_api_export_validation_and_every_file_format():
    result = Analysis.model_validate(analyze_text('We alleviate stress.')).model_dump()
    assert result['items'][0]['synonyms'] == ['relieve']
    document = Document(io.BytesIO(build_docx(result)))
    docx_text = '\n'.join(c.text for table in document.tables for row in table.rows for c in row.cells)
    with fitz.open(stream=build_pdf(result), filetype='pdf') as pdf:
        pdf_text = '\n'.join(page.get_text() for page in pdf)
    csv_rows = list(csv.reader(io.StringIO(build_csv(result).decode('utf-8-sig'))))
    for text in [docx_text, pdf_text, '\n'.join(' '.join(row) for row in csv_rows)]:
        assert 'relieve' in text and 'ease' in text
        assert '同义词' in text

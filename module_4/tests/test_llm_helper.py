"""Test the inherited model adapter using deterministic model responses."""
import json
import sys
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from src.llm_hosting import app as model

pytestmark = pytest.mark.integration


def test_read_lists_and_aliases(tmp_path):
    missing = tmp_path / 'missing.txt'
    with pytest.raises(FileNotFoundError, match='Missing canonical list'):
        model._read_lines(missing)
    missing.write_text(' A \n\nB\n', encoding='utf-8')
    assert model._read_lines(missing) == ['A', 'B']
    assert model.reviewed_university_alias(' MIT ') == 'Massachusetts Institute of Technology'
    assert model.reviewed_university_alias(None) is None
    with pytest.raises(ValueError, match='text or null'):
        model.reviewed_university_alias(5)


def test_model_loader_passes_configuration_and_reuses_instance(monkeypatch):
    download = Mock(return_value='fake-model.gguf')
    constructor = Mock(return_value=object())
    monkeypatch.setitem(sys.modules, 'huggingface_hub', SimpleNamespace(hf_hub_download=download))
    monkeypatch.setitem(sys.modules, 'llama_cpp', SimpleNamespace(Llama=constructor))
    monkeypatch.setattr(model, '_LLM', None)
    first = model._load_llm()
    assert model._load_llm() is first
    assert constructor.call_count == 1
    assert download.call_args.kwargs['revision'] == model.MODEL_REVISION
    assert constructor.call_args.kwargs['model_path'] == 'fake-model.gguf'


@pytest.mark.parametrize('text,expected', [('Mathematics, McG', ('Mathematics', 'Mcgill University')),
    ('Science @ UBC', ('Science', 'University of British Columbia')), ('History', ('History', 'Unknown'))])
def test_fallback_split(text, expected):
    assert model._split_fallback(text) == expected


def test_normalizers(monkeypatch):
    assert model._best_match('', ['A']) is None
    assert model._best_match('Mathematics', []) is None
    assert model._best_match('Mathematic', ['Mathematics']) == 'Mathematics'
    assert model._post_normalize_program('Mathematic') == 'Mathematics'
    assert model._post_normalize_program('A wholly new discipline') == 'A Wholly New Discipline'
    assert model._post_normalize_university('UBC') == 'University of British Columbia'
    assert model._post_normalize_university('McGiill University') == 'McGill University'
    assert model._post_normalize_university('Example Academy') == 'Example Academy'
    assert model._post_normalize_university('') == 'Unknown'
    # Unicode title casing can change dotless i into a canonical Latin I.
    monkeypatch.setattr(model, 'CANON_PROGS', ['I'])
    monkeypatch.setattr(model, 'CANON_UNIS', ['I'])
    assert model._post_normalize_program('ı') == 'I'
    assert model._post_normalize_university('ı') == 'I'


@pytest.mark.parametrize('text', ['prefix {"standardized_program":"Mathematics","standardized_university":"McG"} tail',
    'not JSON', '[]', '{"standardized_program":2,"standardized_university":"U"}',
    '{"standardized_program":"","standardized_university":"U"}', None])
def test_model_response_validation_and_fallback(monkeypatch, text):
    llm = Mock()
    llm.create_chat_completion.return_value = {'choices':[{'message':{'content':text}}]}
    monkeypatch.setattr(model, '_load_llm', lambda: llm)
    result = model._call_llm('Mathematics, McG')
    assert result == {'standardized_program':'Mathematics', 'standardized_university':'McGill University'}
    kwargs = llm.create_chat_completion.call_args.kwargs
    assert kwargs['temperature'] == 0
    assert kwargs['messages'][-1]['role'] == 'user'
    assert json.loads(kwargs['messages'][-1]['content']) == {'program':'Mathematics, McG'}


def test_source_supported_names_and_spelling():
    assert model._source_supported_name('', 'Invented', []) == 'Unknown'
    assert model._source_supported_name('MIT', 'Wrong', model.CANON_UNIS, university=True) == 'Massachusetts Institute of Technology'
    assert model._source_supported_name('McG', 'Wrong', model.CANON_UNIS, university=True) == 'McGill University'
    assert model._source_supported_name('Info Studies', 'Wrong', ['Information Studies']) == 'Information Studies'
    assert model._source_supported_name('Internationall', 'International', ['International']) == 'International'
    assert model._source_supported_name('Information', 'Information Studies', ['Information Studies']) == 'Information'
    assert model._source_supported_name('A campus', 'Other', ['Other']) == 'A campus'
    assert model._source_supported_name(
        'Internationall Relations', 'International Relations', ['International Relations']
    ) == 'International Relations'
    assert model._source_supported_name(
        'International Weird', 'International Studies', ['International Studies']
    ) == 'International Weird'


def test_public_standardizer_preserves_source_meaning(monkeypatch):
    with pytest.raises(ValueError, match='program must be text'):
        model.standardize_program(3)
    assert model.standardize_program('')['standardized_program'] == 'Unknown'
    monkeypatch.setattr(model, '_call_llm', lambda text: {'standardized_program':'Information Studies', 'standardized_university':'McGill University'})
    assert model.standardize_program('Information, McG')['standardized_program'] == 'Information'
    assert model.standardize_program('Information, McG')['standardized_university'] == 'McGill University'


@pytest.mark.parametrize('payload', [None, {}, [2], [{'program':3}], [{'university':4}]])
def test_invalid_input(payload):
    with pytest.raises(ValueError):
        model._normalize_input(payload)


def test_api_and_input_wrapper(monkeypatch):
    monkeypatch.setattr(model, 'standardize_program', lambda *a, **kw: {'standardized_program':'P','standardized_university':'U'})
    client = model.app.test_client()
    assert client.get('/').json == {'ok':True}
    assert client.post('/standardize', json={'rows':[3]}).status_code == 400
    rows = [{'program':'P, U','comments':'Keep me'}, {}]
    response = client.post('/standardize', json={'rows':rows})
    assert response.status_code == 200
    assert response.json['rows'][0]['comments'] == 'Keep me'
    assert response.json['rows'][0]['llm-generated-program'] == 'P'
    assert 'llm-generated-program' not in rows[0]


def test_cli_file_formats_and_source_protection(tmp_path, monkeypatch, capsys):
    source = tmp_path / 'input.json'
    source.write_text(json.dumps([{'program':'P, U'}, {'program':'P, U'}]), encoding='utf-8')
    fake = Mock(return_value={'standardized_program':'P','standardized_university':'U'})
    monkeypatch.setattr(model, 'standardize_program', fake)
    model._cli_process_file(str(source), None, False, False, True)
    output = tmp_path / 'input.json.standardized.json'
    assert len(json.loads(output.read_text())) == 2
    assert fake.call_count == 1
    model._cli_process_file(str(source), None, False, False)
    model._cli_process_file(str(source), None, True, False)
    assert len((tmp_path / 'input.json.jsonl').read_text().splitlines()) == 4
    model._cli_process_file(str(source), None, False, True, True)
    assert len(json.loads(capsys.readouterr().out)) == 2
    with pytest.raises(ValueError, match='Cannot append'):
        model._cli_process_file(str(source), None, True, False, True)
    with pytest.raises(ValueError, match='different files'):
        model._cli_process_file(str(source), str(source), False, False)
    before = output.read_bytes()
    fake.side_effect = RuntimeError('Model interrupted')
    with pytest.raises(RuntimeError):
        model._cli_process_file(str(source), str(output), False, False, True)
    assert output.read_bytes() == before

"""Cleaning, atomic files, model caching and command-line error paths."""
import json
from pathlib import Path
from unittest.mock import Mock
import pytest
from src import clean
from src.llm_hosting import app as model

pytestmark = pytest.mark.integration


def test_clean_preserves_sources_and_normalizes_fields():
    raw = [{'program': '  <b>Computer Science</b>, MIT ', 'status': 'Waitlisted on Sep 1, 2026',
            'Degree': 'Ph.D.', 'term': 'fall 2026', 'GPA': 'GPA 3.9', 'GRE': 'unknown',
            'date_added': 'Added on September 2, 2026', 'comments': '<p>A &amp; B</p>'},
           {'program': None, 'status': 'Accepted on September 3, 2026', 'Degree': "master's"},
           {'program': 'History, Oxford', 'status': 'Rejected on Sep 4, 2026'}]
    before = json.dumps(raw)
    first, second, third = clean.clean_data(raw)
    assert json.dumps(raw) == before
    assert first['program'] == raw[0]['program']
    assert first['raw_program'] == raw[0]['program']
    assert first['program_name'] == 'Computer Science'
    assert first['university'] == 'MIT'
    assert first['comments'] == 'A & B'
    assert first['GPA'] == 3.9
    assert first['GRE'] is None
    assert first['raw_GPA'] == 'GPA 3.9'
    assert first['Degree'] == 'PhD'
    assert first['decision'] == 'Wait listed'
    assert first['start_year'] == 2026
    assert first['date_added_iso'] == '2026-09-02'
    assert first['decision_date_iso'] == '2026-09-01'
    assert second['Degree'] == 'Masters'
    assert second['acceptance_date'] == 'September 3, 2026'
    assert third['rejection_date'] == 'Sep 4, 2026'
    assert clean._date('not a full date') is None
    assert clean._date('2026-09-04') == '2026-09-04'
    assert clean._date('04 Sep 2026') == '2026-09-04'
    assert clean._clean_text('   ') is None
    assert clean._number('-1.2') == -1.2


@pytest.mark.parametrize('rows', [{}, [None], [{'program': 5}]])
def test_reject_bad_input(rows):
    with pytest.raises(ValueError):
        clean.clean_data(rows)


def test_json_roundtrip_and_windows_retry(tmp_path, monkeypatch):
    path = tmp_path / 'nested' / 'records.json'
    real = Path.replace
    calls = []
    def locked_once(source, destination):
        calls.append(destination)
        if len(calls) == 1:
            raise PermissionError('Temporary file lock')
        return real(source, destination)
    sleep = Mock()
    monkeypatch.setattr(Path, 'replace', locked_once)
    monkeypatch.setattr(clean.time, 'sleep', sleep)
    clean.save_data([{'name': 'Café'}], path)
    assert clean.load_data(path) == [{'name': 'Café'}]
    sleep.assert_called_once_with(0.2)
    monkeypatch.setattr(Path, 'replace', Mock(side_effect=PermissionError('Still locked')))
    with pytest.raises(PermissionError):
        clean.save_data([], path)
    assert clean.load_data(path) == [{'name': 'Café'}]
    with pytest.raises(ValueError):
        clean.save_data([float('nan')], path)
    assert clean.load_data(path) == [{'name': 'Café'}]


def test_model_cache_reuse_and_checkpoints(tmp_path, monkeypatch, capsys):
    fake = Mock(side_effect=lambda *a, **kw: {'standardized_program': 'Science', 'standardized_university': 'Example University'})
    monkeypatch.setattr(model, 'standardize_program', fake)
    rows = [{'program': 'Science ' + str(i), 'program_name': 'Science', 'university': 'Example University'} for i in range(100)]
    cache = tmp_path / 'cache.json'
    first = clean.add_llm_fields(rows, cache)
    second = clean.add_llm_fields(rows, cache)
    assert first == second
    assert fake.call_count == 100
    assert first[0]['program'] == rows[0]['program']
    assert 'llm-generated-program' not in rows[0]
    assert first[0]['llm-generated-university'] == 'Example University'
    assert 'Processed 100 of 100' in capsys.readouterr().out
    saved = clean.load_data(cache)
    saved['fingerprint'] = 'stale'
    clean.save_data(saved, cache)
    clean.add_llm_fields(rows[:1], cache)
    assert fake.call_count == 101


@pytest.mark.parametrize('saved', [[], {'results': []}])
def test_bad_cache_rejected(tmp_path, monkeypatch, saved):
    if isinstance(saved, dict):
        saved['fingerprint'] = clean._cache_fingerprint()
    cache = tmp_path / 'cache.json'
    clean.save_data(saved, cache)
    with pytest.raises(ValueError, match='dictionary'):
        clean.add_llm_fields([], cache)


@pytest.mark.parametrize('result', [[], {}, {'standardized_program': '', 'standardized_university': 'U'}])
def test_bad_model_results_rejected_and_cache_saved(tmp_path, monkeypatch, result):
    monkeypatch.setattr(model, 'standardize_program', lambda *a, **kw: result)
    cache = tmp_path / 'cache.json'
    with pytest.raises(ValueError):
        clean.add_llm_fields([{'program': 'P, U'}], cache)
    assert clean.load_data(cache)['results'] == {}


def test_clean_cli(tmp_path, monkeypatch, capsys):
    source, output = tmp_path / 'input.json', tmp_path / 'output.json'
    clean.save_data([{'program': 'P, U'}], source)
    monkeypatch.setattr('sys.argv', ['clean', '--input', str(source), '--output', str(output), '--llm'])
    monkeypatch.setattr(clean, 'add_llm_fields', lambda rows, path: rows)
    clean.main()
    assert clean.load_data(output)[0]['university'] == 'U'
    assert 'Saved 1 applicants' in capsys.readouterr().out
    monkeypatch.setattr('sys.argv', ['clean', '--input', str(source), '--output', str(source)])
    with pytest.raises(SystemExit) as error:
        clean.main()
    assert error.value.code == 2
    for failure in [ValueError('Invalid'), KeyboardInterrupt()]:
        monkeypatch.setattr('sys.argv', ['clean'])
        monkeypatch.setattr(clean, 'load_data', Mock(side_effect=failure))
        with pytest.raises(SystemExit) as error:
            clean.main()
        assert error.value.code == 1
    monkeypatch.setattr(clean, 'load_data', lambda path: [])
    with pytest.raises(SystemExit):
        clean.main()

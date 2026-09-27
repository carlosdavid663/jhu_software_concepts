"""Exercise real script entry points with temporary data and fake servers."""
import json
import runpy
import warnings
from email.message import Message
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from flask import Flask
from src import clean, database
from src.load_data import read_applicants, applicant_records

pytestmark = pytest.mark.integration


def execute(module):
    # Modules are already imported for unit tests; runpy's duplicate-import
    # warning is expected when testing their actual __main__ entry points.
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', message='.*found in sys.modules.*', category=RuntimeWarning)
        return runpy.run_module('src.' + module, run_name='__main__')


def test_database_configuration(monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    with pytest.raises(ValueError, match='Set DATABASE_URL'):
        database.database_url()
    with pytest.raises(ValueError, match='must use PostgreSQL'):
        database.database_url('sqlite:///test.db')
    assert database.database_url('postgresql+psycopg://example/test') == 'postgresql://example/test'
    monkeypatch.setenv('DATABASE_URL', 'postgresql://example/test')
    assert database.database_url() == 'postgresql://example/test'


def test_database_and_query_scripts(db_url, monkeypatch, capsys):
    monkeypatch.setattr('sys.argv', ['script'])
    for name in ['database', 'query_data', 'orm_queries']:
        execute(name)
    output = capsys.readouterr().out
    assert 'Connected to PostgreSQL.' in output
    assert 'Q1.' in output
    assert 'Q11.' in output


def test_join_original_rows_with_llm_names(tmp_path, rows):
    clean.save_data(rows, tmp_path / 'applicant_data.json')
    clean.save_data([dict(rows[0], **{'llm-generated-program':'CS'})], tmp_path / 'llm_extend_applicant_data.json')
    joined = read_applicants(tmp_path)
    assert joined[0]['llm-generated-program'] == 'CS'
    assert joined[1]['llm-generated-program'] is None
    assert joined[0]['program'] == rows[0]['program']


def test_loader_script(db_url, rows, monkeypatch, capsys):
    monkeypatch.setattr(clean, 'load_data', lambda path: rows)
    execute('load_data')
    assert len(applicant_records(db_url)) == 3
    assert 'Inserted 3 new entries' in capsys.readouterr().out


def test_flask_script_does_not_reloader(monkeypatch):
    serve = Mock()
    monkeypatch.setattr(Flask, 'run', serve)
    execute('app')
    assert serve.call_args.kwargs['use_reloader'] is False
    assert serve.call_args.kwargs['host'] == '127.0.0.1'


def test_clean_script(tmp_path, monkeypatch):
    source, target = tmp_path / 'in.json', tmp_path / 'out.json'
    source.write_text('[{"program":"P, U"}]', encoding='utf-8')
    monkeypatch.setattr('sys.argv', ['clean', '--input', str(source), '--output', str(target)])
    execute('clean')
    assert clean.load_data(target)[0]['program_name'] == 'P'


def test_scraper_script_checks_robots_with_fake_http(tmp_path, monkeypatch):
    headers = Message()
    response = Mock(url='https://www.thegradcafe.com/robots.txt', headers=headers)
    response.read.return_value = b'User-agent: *\nAllow: /\n'
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    monkeypatch.setattr('urllib.request.build_opener', lambda *a: SimpleNamespace(open=lambda *a, **kw: response))
    monkeypatch.setattr('sys.argv', ['scrape', '--robots-only', '--data-dir', str(tmp_path)])
    execute('scrape')
    assert clean.load_data(tmp_path / 'robots_check.json')['results_allowed'] is True


def test_pull_script(db_url, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr('src.scrape.check_robots', lambda **kw: (SimpleNamespace(can_fetch=lambda *a: True), 0))
    monkeypatch.setattr('src.scrape._download', lambda url: 'synthetic HTML')
    monkeypatch.setattr('src.scrape.parse_page', lambda *a: [{'url':'https://www.thegradcafe.com/result/9999','program':'P, U'}])
    monkeypatch.setattr('src.scrape.next_page_url', lambda *a: None)
    monkeypatch.setattr('time.sleep', lambda seconds: None)
    monkeypatch.setattr(clean, 'save_data', lambda *a: None)
    monkeypatch.setattr(clean, 'add_llm_fields', Mock(side_effect=RuntimeError('Optional model unavailable')))
    execute('pull_data')
    assert len(applicant_records(db_url)) == 1
    assert 'LLM names were unavailable' in capsys.readouterr().out


def test_llm_script_arguments_files_and_server(tmp_path, monkeypatch, capsys):
    serve = Mock()
    monkeypatch.setattr(Flask, 'run', serve)
    monkeypatch.setattr('sys.argv', ['model', '--serve'])
    execute('llm_hosting.app')
    serve.assert_called_once()
    source = tmp_path / 'input.json'
    source.write_text('[{"program":""}]', encoding='utf-8')
    monkeypatch.setattr('sys.argv', ['model', '--file', str(source), '--stdout', '--json'])
    execute('llm_hosting.app')
    assert json.loads(capsys.readouterr().out)[0]['llm-generated-program'] == 'Unknown'
    for args, code in [(['--json','--append'], 2), (['--stdout','--out','out.json'], 2), (['--file', str(tmp_path/'missing.json')], 1)]:
        monkeypatch.setattr('sys.argv', ['model'] + args)
        with pytest.raises(SystemExit) as error:
            execute('llm_hosting.app')
        assert error.value.code == code

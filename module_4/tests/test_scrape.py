"""Synthetic HTML and injected HTTP responses; never request the live website."""
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.error import URLError
import pytest
from src import scrape
from src.clean import load_data, save_data

pytestmark = pytest.mark.integration
PAGE = scrape.BASE_URL + 'survey/'
ROBOTS = 'User-agent: *\nAllow: /\nDisallow: /private\nCrawl-delay: 3\nRequest-rate: 1/8\n'


def html(ids=(1, 2), next_link=''):
    rows = ''.join(f'''<tr><td>MIT</td><td><span>Computer Science</span><span>PhD</span></td>
        <td>September 20, 2026</td><td>Accepted <a href="/result/{i}">Detail</a></td></tr>
        <tr><td><div>Fall 2026 International GPA 3.9 GRE 165 GRE V 160 GRE AW 4.5</div></td></tr>
        <tr><td><p>Comment with GPA 1.0</p></td></tr>''' for i in ids)
    return '<title>Results</title><table><tr><th>School</th><th>Program</th><th>Date Added</th><th>Decision</th></tr>' + rows + '</table>' + next_link


def test_parser_groups_details_and_ignores_comment_scores():
    records = scrape.parse_page(html(), PAGE)
    assert len(records) == 2
    assert records[0]['url'].endswith('/result/1')
    row = records[0]
    assert row['program'] == 'Computer Science, MIT'
    assert row['Degree'] == 'PhD'
    assert row['GPA'] == '3.9'
    assert row['GRE V'] == '160'
    assert row['comments'] == 'Comment with GPA 1.0'
    assert row['term'] == 'Fall 2026'
    assert row['US/International'] == 'International'
    simple = html((1,)).replace('<span>Computer Science</span><span>PhD</span>', 'Computer Science, Masters')
    assert scrape.parse_page(simple, PAGE)[0]['Degree'] == 'Masters'
    assert scrape._match('missing (word)', 'anything') is None
    assert scrape._NoRedirects().redirect_request(None, None, 302, '', {}, PAGE) is None


@pytest.mark.parametrize('page, message', [('<title>Just a moment</title>', 'verification'), ('<table></table>', 'No results'),
    (html().replace('<th>School</th>', '<th>Unknown</th>'), 'Missing column'),
    (html().replace('/result/1', 'https://evil.example/result/1'), 'Unexpected applicant')])
def test_parser_rejects_changed_or_blocked_html(page, message):
    with pytest.raises(ValueError, match=message):
        scrape.parse_page(page, PAGE)


def test_next_link():
    assert scrape.next_page_url('<a href="?page=2">Next</a>', PAGE) == PAGE + '?page=2'
    assert scrape.next_page_url('<a aria-label="next" href="?page=3">→</a>', PAGE) == PAGE + '?page=3'
    assert scrape.next_page_url('<a href="?page=1">Previous</a>', PAGE) is None
    with pytest.raises(ValueError, match='Unexpected Next'):
        scrape.next_page_url('<a href="https://evil.example">Next</a>', PAGE)


def test_robots_combines_groups_and_uses_specific_rules(tmp_path, monkeypatch):
    monkeypatch.setattr(scrape, '_download', lambda url: ROBOTS)
    parser, delay = scrape.check_robots(2, tmp_path)
    assert delay == 8
    assert not parser.can_fetch(scrape.USER_AGENT, scrape.BASE_URL + 'private')
    assert load_data(tmp_path / 'robots_check.json')['results_allowed'] is True
    parser = scrape._robots_parser('# comment\nUser-agent: *\nDisallow: /\nUser-agent: GradCafeCourseProject\nAllow: /\nUser-agent: GradCafeCourseProject\nDisallow: /private\n')
    assert parser.can_fetch(scrape.USER_AGENT, PAGE)
    assert not parser.can_fetch(scrape.USER_AGENT, scrape.BASE_URL + 'private')
    with pytest.raises(ValueError, match='patterns'):
        scrape._robots_parser('User-agent: *\nDisallow: /*?page=\n')
    for content in ['<html>verification</html>', 'unexpected', 'User-agent: *\nDisallow: /']:
        monkeypatch.setattr(scrape, '_download', lambda url: content)
        with pytest.raises(ValueError):
            scrape.check_robots(data_dir=tmp_path)


def test_http_adapter_validates_urls_and_decodes(monkeypatch):
    headers = Message()
    headers['Content-Type'] = 'text/html; charset=utf-8'
    response = Mock(url=PAGE, headers=headers)
    response.read.return_value = 'Café'.encode()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    opener = Mock()
    opener.open.return_value = response
    monkeypatch.setattr(scrape, 'build_opener', lambda *args: opener)
    assert scrape._download(PAGE) == 'Café'
    assert opener.open.call_args.args[0].get_header('User-agent') == scrape.USER_AGENT
    for url in ['http://www.thegradcafe.com/survey/', 'https://evil.example/survey/', scrape.BASE_URL + 'login']:
        with pytest.raises(ValueError, match='Only GradCafe'):
            scrape._download(url)
    response.url = 'https://evil.example/survey/'
    with pytest.raises(ValueError, match='redirect'):
        scrape._download(PAGE)
    response.url = scrape.BASE_URL + 'login'
    with pytest.raises(ValueError, match='redirected away'):
        scrape._download(PAGE)


def fake_collection(monkeypatch, pages):
    monkeypatch.setattr(scrape, 'check_robots', lambda *a, **kw: (SimpleNamespace(can_fetch=lambda *a: True), 2))
    monkeypatch.setattr(scrape.time, 'sleep', lambda seconds: None)
    monkeypatch.setattr(scrape.time, 'monotonic', lambda: 0)
    fetch = Mock(side_effect=pages)
    monkeypatch.setattr(scrape, '_download', fetch)
    return fetch


def test_default_folders_keep_new_files_together(tmp_path, monkeypatch):
    monkeypatch.setattr(scrape, 'DATA_FOLDER', tmp_path)
    monkeypatch.setattr(scrape, '_download', Mock(return_value=ROBOTS))
    scrape.check_robots()
    assert (tmp_path / 'robots_check.json').exists()

    fake_collection(monkeypatch, [html((1,))])
    applicants = scrape.scrape_data(limit=1)
    assert load_data(tmp_path / 'raw_applicant_data.json') == applicants


def test_collection_resumes_and_deduplicates(tmp_path, monkeypatch):
    fetch = fake_collection(monkeypatch, [html((1, 2), '<a href="?page=2">Next</a>'), html((2, 3))])
    assert len(scrape.scrape_data(3, data_dir=tmp_path)) == 3
    assert (tmp_path / 'saved_pages/page_0001.html').exists()
    assert load_data(tmp_path / 'scrape_progress.json')['next_url'] is None
    assert len(scrape.scrape_data(3, data_dir=tmp_path)) == 3
    assert fetch.call_count == 2
    with pytest.raises(ValueError, match='final results'):
        scrape.scrape_data(4, data_dir=tmp_path)


def test_collection_stops_when_next_links_form_a_cycle(tmp_path, monkeypatch):
    """A -> B -> A must stop before downloading A a second time."""
    first_page = html((1,), '<a href="?page=2">Next</a>')
    second_page = html((2,), '<a href="survey">Next</a>')
    fetch = fake_collection(monkeypatch, [first_page, second_page])

    with pytest.raises(ValueError, match='repeated a page'):
        scrape.scrape_data(10, data_dir=tmp_path)

    assert fetch.call_count == 2
    saved_applicants = load_data(tmp_path / 'raw_applicant_data.json')
    assert len(saved_applicants) == 2


def test_default_scrape_and_clean_commands_use_the_same_data(monkeypatch):
    """Pretend to save a fresh scrape, then clean that exact saved file."""
    from src import clean

    saved_files = {}
    fresh_applicants = [{'program': 'Fresh program, Fresh university'}]

    def pretend_to_scrape(limit, delay, data_dir):
        saved_files[Path(data_dir) / 'raw_applicant_data.json'] = fresh_applicants

    def pretend_to_read(filename):
        return saved_files[Path(filename)]

    save_result = Mock()
    monkeypatch.setattr(scrape, 'scrape_data', pretend_to_scrape)
    monkeypatch.setattr(clean, 'load_data', pretend_to_read)
    monkeypatch.setattr(clean, 'save_data', save_result)

    monkeypatch.setattr('sys.argv', ['scrape'])
    scrape.main()
    monkeypatch.setattr('sys.argv', ['clean'])
    clean.main()

    cleaned_applicants, output_file = save_result.call_args.args
    assert cleaned_applicants[0]['program_name'] == 'Fresh program'
    assert output_file.parent / 'raw_applicant_data.json' in saved_files


@pytest.mark.parametrize('raw,progress,message', [({}, None, 'JSON array'), ([None], None, 'JSON array'), ([{}], None, 'text URL'),
    ([{'url':'a'},{'url':'a'}], None, 'duplicate'), ([{'url':'a'}], None, 'without scrape_progress'),
    ([], {}, 'Invalid checkpoint'), ([], {'next_page':2,'next_url':PAGE}, 'without its matching'),
    ([{'url':'a'}], {'next_page':0,'next_url':PAGE}, 'invalid page number')])
def test_invalid_checkpoints_preserve_data(tmp_path, raw, progress, message):
    save_data(raw, tmp_path / 'raw_applicant_data.json')
    if progress is not None:
        save_data(progress, tmp_path / 'scrape_progress.json')
    with pytest.raises(ValueError, match=message):
        scrape.scrape_data(10, data_dir=tmp_path)
    assert load_data(tmp_path / 'raw_applicant_data.json') == raw


def test_collection_rejection_and_no_next_link(tmp_path, monkeypatch):
    fake_collection(monkeypatch, [html((1,))])
    with pytest.raises(ValueError, match='No new Next'):
        scrape.scrape_data(3, data_dir=tmp_path)
    assert len(load_data(tmp_path / 'raw_applicant_data.json')) == 1
    monkeypatch.setattr(scrape, 'check_robots', lambda *a: (SimpleNamespace(can_fetch=lambda *a: False), 2))
    with pytest.raises(ValueError, match='disallows the next'):
        scrape.scrape_data(3, data_dir=tmp_path / 'denied')


def test_recovery_after_data_saved_before_checkpoint(tmp_path, monkeypatch):
    data = scrape.parse_page(html((1,)), PAGE)
    save_data(data, tmp_path / 'raw_applicant_data.json')
    save_data({'next_page':1,'next_url':PAGE}, tmp_path / 'scrape_progress.json')
    fake_collection(monkeypatch, [html((1,), '<a href="?page=2">Next</a>'), html((2,))])
    assert len(scrape.scrape_data(2, data_dir=tmp_path)) == 2
    save_data({'next_page':1,'next_url':PAGE+'?other'}, tmp_path / 'scrape_progress.json')
    fake_collection(monkeypatch, [html((1,))])
    with pytest.raises(ValueError, match='adds no new'):
        scrape.scrape_data(3, data_dir=tmp_path)


def test_scrape_cli(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr('sys.argv', ['scrape', '--limit', '0'])
    with pytest.raises(SystemExit) as error:
        scrape.main()
    assert error.value.code == 2
    monkeypatch.setattr('sys.argv', ['scrape', '--robots-only', '--data-dir', str(tmp_path)])
    monkeypatch.setattr(scrape, 'check_robots', Mock())
    scrape.main()
    assert 'Saved robots.txt' in capsys.readouterr().out
    monkeypatch.setattr('sys.argv', ['scrape', '--data-dir', str(tmp_path)])
    monkeypatch.setattr(scrape, 'scrape_data', Mock(return_value=[]))
    scrape.main()
    for failure in [URLError('Blocked'), KeyboardInterrupt()]:
        monkeypatch.setattr(scrape, 'scrape_data', Mock(side_effect=failure))
        with pytest.raises(SystemExit) as error:
            scrape.main()
        assert error.value.code == 1

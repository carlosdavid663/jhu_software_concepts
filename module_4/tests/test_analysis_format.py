"""Labels, rounding, missing values and all eleven question identities."""
import re
from unittest.mock import Mock
from decimal import Decimal
from bs4 import BeautifulSoup
import pytest
from src.app import create_app
from src.query_data import QUERIES, format_value, formatted_rows, print_results

pytestmark = pytest.mark.analysis


@pytest.mark.parametrize("value,kind,expected", [(Decimal('39.278'), 'percent', '39.28%'), (0, 'percent', '0.00%'),
    (100, 'percent', '100.00%'), (None, 'percent', 'N/A'), (3.456, 'decimal', '3.46'),
    (1200, 'count', '1200'), ('Masters', 'text', 'Masters')])
def test_format_value(value, kind, expected):
    assert format_value(value, kind) == expected


def test_all_cards_label_answers_and_percentages():
    # Give every question one answer row, with a value for each column.
    values = {}
    for question in QUERIES:
        answer_row = []
        for display_format in question['formats']:
            if display_format == 'text':
                answer_row.append('Accepted')
            else:
                answer_row.append(Decimal('39.278'))
        values[question['number']] = [answer_row]

    app = create_app({"TESTING": True}, query=Mock(return_value=values))
    page = BeautifulSoup(app.test_client().get('/analysis').data, 'html.parser')
    cards = page.select('[data-testid="analysis-item"]')
    assert len(cards) == 11
    for card in cards:
        assert 'Answer:' in card.get_text()
    percentages = re.findall(r'\d+(?:\.\d+)?%', page.get_text())
    assert percentages == ['39.28%', '39.28%']
    for percentage in percentages:
        assert re.fullmatch(r'\d+\.\d{2}%', percentage)


def test_console_formatting(capsys):
    results = {}
    for question in QUERIES:
        missing_values = []
        for display_format in question['formats']:
            missing_values.append(None)
        results[question['number']] = [missing_values]
    print_results(results, 'Analysis', numbers=[1])
    output = capsys.readouterr().out
    assert 'Q1.' in output
    assert 'Q2.' not in output
    assert 'Entries: N/A' in output
    assert formatted_rows(QUERIES[0], [(5,)]) == [['5']]

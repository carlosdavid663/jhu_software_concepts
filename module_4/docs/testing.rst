Testing guide
=============

Run the entire suite from ``module_4``::

   python -m pytest
   python -m pytest -m "web or buttons or analysis or db or integration"

Both commands cover every source module and enforce 100% line coverage. There
are no source exclusions. The suite currently contains 101 tests. Pytest's
``conftest.py`` rejects any test without at least one assignment marker.

Markers
-------

``web``
   Factory configuration, routes, static assets, HTML and stable selectors.

``buttons``
   Successful pulls/updates, worker failures and busy-state behavior.

``analysis``
   Answer labels, percentages, rounding and display formatting.

``db``
   Real schema, insertion, uniqueness, rollback and SQL/ORM results.

``integration``
   Pull/update/render flows, ETL, model boundaries and script commands.

For a focused development check use ``python -m pytest -m buttons --no-cov``.
The coverage threshold applies to the complete suite, so partial runs should
explicitly disable coverage or will correctly report uncovered application code.

Fixtures and injection
----------------------

``rows``
   Three synthetic applicant records with known terms, decisions, scores and
   classifications. They are independent of the large supplied data files.

``db_url``
   Requires an explicitly configured PostgreSQL test database ending in
   ``_test``. Creates a random schema, sets its search path, and removes only
   that schema after the test. A missing database fails the test, never skips it.

``no_live_scraping``
   Replaces urllib's live request boundary with a failure. Parser tests supply
   synthetic HTML; HTTP-adapter tests supply response objects. Model tests
   replace model responses and downloads. No live inference is required.

Factory callbacks
   ``scraper()`` returns rows; ``loader(rows)`` returns ``(inserted, skipped)``;
   ``query()`` returns a dictionary keyed by question numbers 1 through 11;
   ``runner(work)`` schedules the provided callable. Tests use a list's
   ``append`` method as a runner, inspect busy state, and invoke the queued
   function explicitly. No arbitrary sleep is used to establish busy state.

Stable selectors
----------------

* ``[data-testid="pull-data-btn"]``
* ``[data-testid="update-analysis-btn"]``
* ``[data-testid="analysis-item"]``
* ``[data-question="2"]`` for a particular analysis question.
* ``[role="status"]`` for the user-visible operation status.

Assertions use Flask's test client and BeautifulSoup. Every card includes an
``Answer:`` label. Percentages must match ``\d+\.\d{2}%``; missing denominators
display ``N/A`` instead of a misleading zero percentage.

Evidence and CI
---------------

``coverage_summary.txt`` is the recorded local marked-suite output.
The root GitHub workflow uses a disposable PostgreSQL service and executes
the same suite, followed by a strict Sphinx build. ``actions_success.png`` must
be a screenshot of an actual successful remote run; it is pending until the
repository is accessible and the workflow has run.

Coverage verifies executed Python statements. Browser JavaScript and model
quality are outside that measurement; no browser clicks are needed by this
test suite.

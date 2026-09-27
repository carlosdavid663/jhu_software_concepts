Operational notes and troubleshooting
=====================================

Busy policy
-----------

One lock per Flask app protects the pull flag and analysis state. Starting a
pull claims the busy flag before scheduling the worker. Both POST routes
reject work while it is set. Success, worker exceptions and scheduling errors
release it. The current design requires one application process; a multiworker
deployment would need a shared job queue and shared lock.

Idempotency and atomicity
-------------------------

The entry URL is the uniqueness key. ``ON CONFLICT (url) DO NOTHING`` makes
repeated pulls safe. This preserves the first stored version of an entry; it
does not update existing rows after a source edit. Records without a URL are
skipped. A failed insert rolls back the entire batch, including inserts that
preceded the failing row. Source JSON writes use a temporary file and atomic
replacement. Successful partial model cache work is retained for reuse.

Collection and data limitations
-------------------------------

The scraper checks robots rules, enforces delays and stops on blocks or
unexpected redirects. Site changes may require parser updates. The incremental
collector assumes newest-first ordering and stops at a fully known page.
It does not revisit older edited entries. Model names can be missing after
optional inference fails. Questions using model names then exclude those
missing values. Stored GRE scores remain source reports, including implausible
values; consult the included ``limitations.pdf`` before interpreting averages.

Standalone ``python -m src.scrape`` and ``python -m src.clean`` share
``runtime/collection``. Use explicit ``--input`` and ``--output`` paths when
cleaning a custom collection folder. Both collectors reject repeated page
URLs during a run. The bulk collector retains completed records and supports
restarting from its saved checkpoint.

Troubleshooting
---------------

``Set DATABASE_URL`` or connection refused
   Set the URL in the same terminal running the command. Verify PostgreSQL is
   running, the port/database exist, and your account can connect. Use
   ``python -m src.database`` to check. Do not include credentials in logs.

Missing ``applicants`` table
   Run ``python -m src.load_data`` once against the application database.

Tests require ``TEST_DATABASE_URL``
   Create a separate database ending in ``_test`` and give the test user schema
   creation permission. Tests deliberately refuse the application database.

Coverage fails after adding code
   Add behavioral tests for the new success and error paths, then run the
   entire marked suite. A selected subset does not establish full coverage.

LLM dependency or model download failure
   Install ``requirements-llm.txt`` if new standardization is needed. The
   analytics app still loads existing supplied names and saves usable cleaned
   rows with a warning when new names cannot be generated.

GitHub workflow absent
   Verify the file is at ``.github/workflows/tests.yml`` in the repository root,
   Actions is enabled, and the pushed branch includes it. Check the service
   health step and test output if a run fails.

Read the Docs import/build failure
   Check repository access, root ``.readthedocs.yaml``, Python version and the
   Sphinx build log. ``conf.py`` resolves paths relative to itself. Importing
   source modules performs neither database queries nor model downloads.

Reference documentation
-----------------------

* `Pytest markers <https://docs.pytest.org/en/stable/how-to/mark.html>`_
* `Sphinx autodoc <https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html>`_
* `GitHub PostgreSQL service containers <https://docs.github.com/en/actions/tutorials/use-containerized-services/create-postgresql-service-containers>`_
* `Read the Docs configuration <https://docs.readthedocs.com/platform/stable/config-file/v2.html>`_

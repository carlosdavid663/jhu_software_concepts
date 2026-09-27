# Module 4 - Testing and documentation

Carlos David Arredondo Vazquez

This extends the Module 3 Grad Cafe application with a Flask app factory,
deterministic Pytest tests, real PostgreSQL integration tests, and Sphinx docs.
All eleven analysis questions and the original fifteen-column PostgreSQL
schema are retained.

**Verified locally:** 101 tests pass; all 1,218 Python statements under `src/` are
covered (100% line coverage). This includes the inherited local model helper.
No source files or lines are excluded from coverage. See
[coverage_summary.txt](coverage_summary.txt).

**GitHub Actions:** the [successful workflow run](https://github.com/carlosdavid663/jhu_software_concepts/actions/runs/36315696953)
is recorded in [actions_success.png](actions_success.png).
The documentation is published at the link below.

Repository SSH URL recorded in Module 3:
`git@github.com:carlosdavid663/jhu_software_concepts.git`

Hosted documentation: [Grad Cafe - Module 4](https://module-4-testing-and-documentation-assignment.readthedocs.io/en/latest/).
Generated local documentation: [open the HTML](docs/_build/html/index.html).

## Install and configure

Use Python 3.12 and PostgreSQL 18. From this `module_4` folder:

```text
python -m venv .venv
```

Activate it on Windows with `.venv\Scripts\activate`, or on macOS/Linux with
`source .venv/bin/activate`, then install:

```text
python -m pip install -r requirements.txt
```

Create a normal application database and a separate test database, using a
PostgreSQL account permitted to create them:

```text
createdb gradcafe_module4
createdb gradcafe_module4_test
```

Set your actual connection URL in the terminal. Keep credentials out of code,
GitHub and the ZIP. These examples assume PostgreSQL's local authentication
already identifies your account; otherwise supply your own username and
password in the URL or use PostgreSQL's password file.

PowerShell:

```powershell
$env:DATABASE_URL = 'postgresql://localhost:5432/gradcafe_module4'
$env:TEST_DATABASE_URL = 'postgresql://localhost:5432/gradcafe_module4_test'
```

macOS/Linux:

```sh
export DATABASE_URL='postgresql://localhost:5432/gradcafe_module4'
export TEST_DATABASE_URL='postgresql://localhost:5432/gradcafe_module4_test'
```

Unlike Module 3, this version uses `DATABASE_URL` rather than a saved personal
connection file. The test account needs permission to create schemas in the
test database. Its database name must end in `_test`. Tests create and remove
their own randomly named schemas; they never reset the application's tables.

## Load data and open the app

```text
python -m src.database
python -m src.load_data
python -m src.app
```

Open <http://127.0.0.1:5000/analysis>. `Pull Data` starts collection in a
background thread. `Update Analysis` refreshes the displayed answers after
collection finishes. Both requests return 409 while a pull is running.

The bundled data files are copied from Module 3. `load_data` joins the
standardized names by entry URL and inserts each URL once. Re-running it is
safe: existing URLs are ignored. `limitations.pdf` explains the source-data
limitations, including self-selection and unverified scores.

Optional new local LLM inference:

```text
python -m pip install -r requirements-llm.txt
```

The first inference can download the model. Without these optional packages,
Pull Data retains cleaned entries and displays a warning that new LLM names
are missing. Loading the supplied data, testing and building documentation do
not require a model download. New batches are written under `runtime/`.

Additional commands, run from `module_4`:

```text
python -m src.query_data
python -m src.orm_queries
python -m src.clean --input raw_applicant_data.json --output runtime/cleaned.json
python -m src.scrape --data-dir runtime/fresh --limit 20
```

For a fresh collection using the shared default folder, run these in order:

```text
python -m src.scrape --limit 20
python -m src.clean
```

Both commands use `runtime/collection/`, preserving the original submitted
JSON files. To add new model names afterward, use `python -m src.clean --llm`
with the optional model dependencies installed. If you choose a custom
scraper folder, pass its raw file to the cleaner with `--input` and choose
`--output` explicitly. The standalone loader still loads the bundled files;
the website's Pull Data button loads its fresh batches automatically.

## Run tests

```text
python -m pytest
python -m pytest -m "web or buttons or analysis or db or integration"
```

Both commands execute the entire suite with a 100% coverage threshold. Every
test has one of the five registered markers; collection rejects unmarked tests.
The suite uses synthetic records and HTML, fakes model responses, and prevents
live urllib requests. PostgreSQL database tests are real and are never silently
skipped when the database is missing.

For one category while developing (partial coverage is expected):

```text
python -m pytest -m buttons --no-cov
```

The five specifically requested files are present:
`test_flask_page.py`, `test_buttons.py`, `test_analysis_format.py`,
`test_db_insert.py`, and `test_integration_end_to_end.py`.
Additional tests cover inherited ETL, the model adapter and script entry points.

## Build documentation

```text
python -m sphinx -W --keep-going -b html docs docs/_build/html
```

Open `docs/_build/html/index.html`. The docs cover setup, architecture,
all application modules, HTTP routes, tests, fixtures, selectors and operations.

For Read the Docs, place `.readthedocs.yaml` at the **repository root**, import
the repository in your Read the Docs account, and build the chosen branch.
The published documentation is linked near the top of this README.
The configuration does not connect to a database or load a model during import.

## GitHub Actions and submission

Place `.github/workflows/tests.yml` at the **repository root**, alongside
`module_4`, not inside it. The job starts PostgreSQL, runs all marked tests with
100% coverage, and builds Sphinx with warnings treated as errors.

The supplied archive includes both repository-root configuration files.
The successful run is saved as `module_4/actions_success.png`. The screenshot
and coverage summary are included in this package. After pushing changes,
confirm the new GitHub Actions run and Read the Docs build succeed.
Check that the ZIP and committed files match before submitting to Canvas.

Submit the repository SSH URL, hosted documentation link, and matching
project ZIP to Canvas.

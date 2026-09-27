Setup and daily use
===================

Prerequisites
-------------

Use Python 3.12 and PostgreSQL 18. Run commands from ``module_4``.
Create and activate a Python virtual environment, then install the required
packages::

   python -m venv .venv
   python -m pip install -r requirements.txt

Between those commands, activate ``.venv\Scripts\activate`` on Windows or
``source .venv/bin/activate`` on macOS/Linux. Create separate application and
test databases with ``createdb gradcafe_module4`` and
``createdb gradcafe_module4_test``. Use your configured PostgreSQL account.

Environment variables
---------------------

``DATABASE_URL``
   PostgreSQL URL for application commands. Example without embedded credentials:
   ``postgresql://localhost:5432/gradcafe_module4``. Supply your own account or
   password file if local authentication requires it. No personal settings
   file is read automatically.

``TEST_DATABASE_URL``
   Separate database URL for tests. Its database name must end in ``_test``.
   The test user must be able to create and drop schemas in that database.
   Example: ``postgresql://localhost:5432/gradcafe_module4_test``.

Optional model settings
   ``MODEL_REPO``, ``MODEL_FILE``, ``MODEL_REVISION``, ``N_THREADS``, ``N_CTX``
   and ``N_GPU_LAYERS`` configure new inference. ``CANON_UNIS_PATH`` and
   ``CANON_PROGS_PATH`` override the bundled reference lists. ``PORT`` controls
   the optional model HTTP server; it does not change the analytics app port.

PowerShell uses ``$env:DATABASE_URL = 'your URL'``; a POSIX shell uses
``export DATABASE_URL='your URL'``. Do not commit passwords or environment files.

Run the application
-------------------

Load the supplied Module 3 data and start the app::

   python -m src.database
   python -m src.load_data
   python -m src.app

Visit ``http://127.0.0.1:5000/analysis``. Use a single process with the reloader
disabled. Pull Data schedules collection; Update Analysis refreshes results.
The program and standardized-name JSON files stay in the ``module_4`` folder.
Newly collected batches are saved in ``runtime``.

New LLM names require the optional dependencies::

   python -m pip install -r requirements-llm.txt

The model is downloaded lazily on first inference. Without it, a pull can still
save cleaned entries with missing LLM fields and an explanatory warning.

Run tests and build docs
------------------------

With ``TEST_DATABASE_URL`` configured::

   python -m pytest
   python -m sphinx -W --keep-going -b html docs docs/_build/html

Open ``docs/_build/html/index.html``. The docs build needs no database or model.

Publishing
----------

The repository-root ``.readthedocs.yaml`` installs the main requirements and
points to this Sphinx configuration. Import the repository in a Read the Docs
account, choose the branch, build it, and put the actual successful URL in the
README. Publishing and repository visibility changes are separate account
actions; generated local HTML alone does not satisfy the hosted-link requirement.

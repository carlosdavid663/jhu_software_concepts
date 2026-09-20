# Module 3 - Database Queries

Carlos David Arredondo Vazquez

This project puts the Grad Cafe data from Module 2 into PostgreSQL, answers
11 questions, and displays the results on a Flask webpage.

**New computer:** follow steps 1-4 below. Steps 1-3 are one-time setup.
**Already set up:** go to "Opening the webpage again" below. The scripts read
your saved connection automatically, including in a new terminal.

## What to read first

1. `load_data.py` puts the data into the database.
2. `query_data.py` answers the questions with ordinary SQL.
3. `models.py` describes one applicant as a Python class.
4. `orm_queries.py` answers the same questions using that class.
5. `app.py` connects those functions to the webpage and its two buttons.

`database.py` holds the shared connection settings. `pull_data.py` collects and
loads new entries when you click Pull Data.

The new scripts use functions, dictionaries, and loops. The larger files under
`llm_hosting/` are the supplied Module 2 model helper; you do not need to rewrite them.

## 1. Install the tools

Use 64-bit Python 3.12 and PostgreSQL. This project was tested on Windows with
PostgreSQL 18.6, psycopg 3.3.6, SQLAlchemy 2.0.54, and Flask 3.1.3.

If PostgreSQL is not installed, get it from the
[official Windows download page](https://www.postgresql.org/download/windows/).
Remember the password you choose for the `postgres` user. Keep the default port
`5432` unless another PostgreSQL installation already uses it.

Open a PowerShell terminal in this `module_3` folder. Create a Python environment
and install the libraries:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

These commands use the environment's Python directly, so activation is unnecessary.
The local LLM library is included for Pull Data. Reading the supplied data and
running the analyses do not download or rerun the model.

## 2. Create the database once

For a normal PostgreSQL 18 Windows installation:

```powershell
& "C:\Program Files\PostgreSQL\18\bin\createdb.exe" -U postgres gradcafe
```

Enter your PostgreSQL password when asked. If you installed another PostgreSQL
version, replace `18` in the path. If the message says the database already exists,
continue to the next step. The loader will create the `applicants` table.

## 3. Connection details are predefined

These values are already filled in at the top of `database.py`:

| Setting | Default value |
| --- | --- |
| Host | `localhost` |
| Port | `5432` |
| Database | `gradcafe` |
| Username | `postgres` |

**You do not enter these values in each terminal.** Every script uses
`database.py`, which also reads the saved password automatically. Both psycopg
and SQLAlchemy use this same connection.

The password file belongs in your Windows user folder:
`C:\Users\YOUR_NAME\.gradcafe\connection.json`. Replace `YOUR_NAME` with your
Windows account name. If this computer already has that file, continue to step 4.

On a new computer, complete steps 1-2, then save that computer's PostgreSQL
password once. Create the `.gradcafe` folder inside your Windows user folder,
and create a file called `connection.json` inside it containing:

```json
{"password": "YOUR_POSTGRESQL_PASSWORD"}
```

Replace the example password with the actual one. If you use Notepad, choose
"All files" when saving so the filename ends in `.json`, not `.json.txt`.
Keep this file outside the project, GitHub, and the submission ZIP. It is read
automatically on later runs. The code does not contain a password or install
PostgreSQL for you.

An existing local file can also override the host, port, database (`dbname`),
and username (`user`) for a computer that uses different settings. The predefined
values above apply when the file does not override them.

Optional connection check, with PostgreSQL running:

```powershell
.\.venv\Scripts\python.exe database.py
```

This checks the saved connection without asking questions or changing settings.
Advanced use only: terminal variables such as `PGDATABASE` and `PGPASSWORD` take
priority over the saved file. They are optional and let tests use a separate database.

## 4. Load the data and run the analyses

Run each line separately:

```powershell
.\.venv\Scripts\python.exe load_data.py
.\.venv\Scripts\python.exe query_data.py
.\.venv\Scripts\python.exe orm_queries.py
.\.venv\Scripts\python.exe app.py
```

The first command inserts 30,020 entries into an empty database. Running it again
inserts zero duplicates. The SQL script prints all 11 questions. The ORM script
prints the required six: Q1, Q4, Q5, Q8, Q9, and the additional Q10. All 11 ORM
queries are also implemented because the webpage needs them.

Leave the last command running and open **http://127.0.0.1:5000** in your browser.
Press `Ctrl+C` in the terminal when you want to stop the webpage.

## Opening the webpage again

After setup and the first data load, make sure PostgreSQL is running. Open a
terminal in `module_3` and run:

```powershell
.\.venv\Scripts\python.exe app.py
```

Open **http://127.0.0.1:5000** and leave the terminal open while using the page.
You do not need to repeat installation, create the database again, reload the
included data, or enter connection settings each time.

## What the two buttons do

- **Pull Data:** starts one background worker, checks the site's robots rules,
  reads the newest public results, cleans new entries, adds their LLM names,
  and inserts them into PostgreSQL. It stops at a complete page of known URLs.
- **Update Analysis:** runs the ORM queries again and shows the latest database
  results. It does not download data.

While a pull is running, both buttons are disabled. The page checks progress
every five seconds and keeps the previous analysis visible. When the pull ends,
click Update Analysis. Duplicate URLs are also rejected by a database constraint.

The scraper waits at least five seconds between page requests, follows any longer
robots delay, and stops on blocked or unexpected responses. A first model download
is about 640 MiB, so the first pull with unfamiliar program names can take longer.
Keep the terminal open until the pull finishes. Run only one copy of `app.py`;
the simple thread lock is designed for this single-process classroom application.

New batches and model answers are saved in `runtime/`, and model weights are saved
in `llm_hosting/models/`. These generated folders are excluded from the submission.
The three original JSON files stay unchanged. The pull assumes the public listing
is ordered newest first; it does not revisit every old entry to find later edits.

If the model cannot generate names, Pull Data still saves the usable cleaned entries.
Their two LLM name fields are left blank, and the page shows a warning. These entries
can appear in the other analyses but cannot match the LLM count in Q9. That warning
is also explained beside Q9. Missing names are not filled automatically by later pulls.

## Where the data comes from

The included Module 2 snapshot contains **30,020 entries**, dated January 19 through
September 12, 2026. An entry is one reported application result, not necessarily
one unique person.

- `raw_applicant_data.json`: original collected records, retained from Module 2.
- `applicant_data.json`: the cleaned base data loaded by this assignment.
- `llm_extend_applicant_data.json`: supplies the two extra name fields for Q9.

The loader joins the last two files by `url`. It preserves the original `program`
text. `status` is shortened from text such as `Accepted on September 11, 2026`
to `Accepted`, and blank optional fields become SQL `NULL`.

The table follows the PDF: `p_id` is an automatically generated integer primary
key; `date_added` is a date; `gpa`, `gre`, `gre_v`, and `gre_aw` are floating-point
numbers; all other listed fields are text. `url` is additionally unique.
JSON `US/International`, `Degree`, `GPA`, `GRE`, `GRE V`, and `GRE AW` map to
`us_or_international`, `degree`, `gpa`, `gre`, `gre_v`, and `gre_aw` respectively.
The hyphenated LLM JSON field names become the two underscore names in the table.

Each average independently ignores missing values. International percentage uses
American, International, and Other as its denominator; Other is not international.
Fall 2025 acceptance percentage uses **all** Fall 2025 entries as its denominator.
Q7 and Q8 use original names; Q9 uses the LLM names. Names are matched without
case sensitivity, with common aliases such as JHU, MIT, CMU, and CS.

Scores are loaded as supplied, including numeric values outside expected GRE
ranges. The Q3 averages therefore describe the stored fields, not verified test
scores. See `limitations.pdf` for the specific effects. No scores are invented,
clamped, or converted between scales.

## SQL and ORM comparison (Q4)

SQL:

```sql
SELECT AVG(gpa) FROM applicants
WHERE term ILIKE 'Fall 2026'
  AND us_or_international ILIKE 'American';
```

SQLAlchemy ORM:

```python
statement = select(func.avg(Applicant.gpa)).where(
    Applicant.term.ilike("Fall 2026"),
    Applicant.us_or_international.ilike("American"),
)
with Session() as session:
    result = session.scalar(statement)
```

Both queries calculate the same average and ignore missing GPAs.
SQL is useful because the database operations are written directly and can be
copied into a database tool. The ORM is useful because Python code refers to the
Applicant model and can reuse its expressions in the webpage. SQL is shorter
for this small query, while the ORM fits naturally with the rest of the Python app.

## Results, checks, and submission

`query_results.pdf` contains all 11 questions, results, executable SQL, and explanations.
`limitations.pdf` contains two paragraphs about bias, missing data, and score quality.
The PDFs and screenshots describe the original 30,020-entry snapshot. Later pulls
can change the local database and webpage results.

Validation included all 11 SQL/ORM outputs, a repeated full-data load, and 22
checks covering known-answer fixtures, missing values, zero denominators,
transaction rollback, overlapping pulls, and error recovery. Live collection was
also exercised in a separate test database so the report snapshot stayed unchanged.
That live test added 4 new entries on the first pull and 0 on the next pull.
The model-failure check also confirms that usable entries load with blank LLM
names, repeated imports add no duplicates, and the page retains the warning.
Connection checks cover predefined defaults, automatic saved settings, terminal
overrides for a separate test database, and connection checks without input prompts.

The evidence is under `screenshots/`: SQL console output (two images), ORM console
output, and the running Flask page. The SQL/ORM images show the scripts' actual
standard output displayed in a browser viewer, labelled as captured output;
they are not screenshots of a native terminal. To capture native terminal images
instead, run the two query commands in step 4 and use Windows Snipping Tool.

Upload this complete `module_3` folder to the private course repository and submit
`module_3.zip` as requested. `github.txt` contains the repository SSH URL. Keep the
GitHub files and ZIP version the same, and ensure the grader has access. Do not
include `.venv`, `__pycache__`, `runtime`, downloaded model weights, or passwords.

## If something does not work

- **Connection refused:** start PostgreSQL and check that its host and port match the configured values.
- **Password authentication failed:** check the password in your local `connection.json` file.
- **Relation applicants does not exist:** run `load_data.py` first.
- **Port 5000 is already in use:** stop an earlier copy of this Flask app.
- **Pull failed:** read the terminal error. Network blocks or an unavailable model
  have different outcomes: a blocked scrape stops the pull; an unavailable model
  allows cleaned entries to be saved with blank LLM names. Existing database rows
  remain protected from duplicate insertion.

References: [psycopg](https://www.psycopg.org/psycopg3/docs/),
[SQLAlchemy](https://docs.sqlalchemy.org/en/20/orm/),
[Flask](https://flask.palletsprojects.com/en/stable/),
[ETS score ranges](https://www.ets.org/gre/test-takers/general-test/scores/get-scores.html).

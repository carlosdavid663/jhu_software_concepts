Architecture
============

Web layer
---------

``src.app.create_app`` creates a fresh Flask app, state dictionary and lock.
The Analysis page shows the most recent complete query result. The two POST
routes return JSON; a small browser script submits the forms and reloads the
Analysis page. While collection runs, the page refreshes every five seconds
and both buttons are disabled. The server also enforces busy gating, so
requests cannot bypass it by ignoring the disabled buttons.

ETL layer
---------

``scrape`` downloads only allowed Grad Cafe public endpoints, records robots
evidence, parses result tables and follows actual Next links. ``pull_data``
stops when it reaches an already-known page. ``clean`` preserves original
program names, removes HTML from derived fields and normalizes dates/scores.
The optional local model adds names while retaining source fields. Tests
replace website and model boundaries with deterministic responses.

``src.paths`` defines the shared standalone collection folder,
``runtime/collection``. The default scrape and clean commands both use it;
the original submitted JSON files remain separate. Each bulk scrape also
tracks pages visited during that run, stopping an A -> B -> A cycle before
requesting A again. It still supports resuming a previously saved page after
an interrupted checkpoint write.

Database and analysis layers
----------------------------

``load_data`` converts JSON fields into the original Module 3 table and inserts
a batch in one PostgreSQL transaction. ``url`` is unique, so repeated pulls
cannot create duplicates. ``query_data`` implements eleven SQL questions;
``orm_queries`` provides equivalent SQLAlchemy expressions. The web app uses
ORM queries in a repeatable-read snapshot. Display formatting is shared.

Data flow::

   Pull Data -> scraper -> cleaner -> optional LLM -> transactional loader
                                                          |
                                                     PostgreSQL
                                                          |
   Analysis HTML <- common formatting <- Update Analysis / ORM queries

Schema contract
---------------

The ``applicants`` table retains these fields:

* ``p_id``: generated integer primary key, not null.
* ``url``: unique text identity, not null.
* ``program``, ``comments``, ``status``, ``term``, ``us_or_international``:
  nullable text. Unknown source values remain missing.
* ``date_added``: nullable SQL date.
* ``gpa``, ``gre``, ``gre_v``, ``gre_aw``: nullable double precision.
* ``degree``, ``llm_generated_program``, ``llm_generated_university``:
  nullable text.

No extra non-null constraints are imposed on legitimately missing source data.
The loader skips entries without URLs, normalizes known decision labels, and
preserves original program spelling. A database error rolls back the whole batch.

API reference
=============

HTTP routes
-----------

``GET /analysis`` and ``GET /``
   Return the Analysis page with HTTP 200. On initial load, query the database
   when idle. Database failures show a useful message without discarding prior
   results. The static CSS and JavaScript are served under ``/static/``.

``POST /pull-data`` and legacy ``POST /pull``
   Return HTTP 202 with ``{"ok": true}`` after scheduling a background pull.
   A synchronous test configuration returns HTTP 200 after success or 500 on
   failure. If already busy, return 409 with ``{"busy": true}`` and do no work.
   A worker-start failure returns 500. An accepted asynchronous request can
   later fail; its outcome is shown by the Analysis page's status message.

``POST /update-analysis`` and legacy ``POST /update``
   Return HTTP 200 with ``{"ok": true}`` after refreshing. Return 409 with
   ``{"busy": true}`` during a pull, or 500 with ``{"ok": false}`` on query
   failure. Failed queries retain the previous complete result and timestamp.

These POST endpoints accept no request-body parameters. Their GET methods
return 405. The optional model server separately provides ``GET /`` for health
and ``POST /standardize`` for a row array or ``{"rows": [...]}`` payload.

Flask application
-----------------

.. automodule:: src.app
   :members:

Shared data folders
-------------------

.. automodule:: src.paths
   :members:

Scraping
--------

.. automodule:: src.scrape
   :members:

Cleaning and model caching
--------------------------

.. automodule:: src.clean
   :members:

Database connection
-------------------

.. automodule:: src.database
   :members:

Loading and record dictionaries
-------------------------------

.. automodule:: src.load_data
   :members:

SQL queries and display formatting
----------------------------------

.. automodule:: src.query_data
   :members:

ORM model and queries
---------------------

.. autoclass:: src.models.Applicant

.. automodule:: src.orm_queries
   :members:

Incremental pulls
-----------------

.. automodule:: src.pull_data
   :members:

Optional model adapter
----------------------

.. automodule:: src.llm_hosting.app
   :members: standardize_program, reviewed_university_alias, health, standardize

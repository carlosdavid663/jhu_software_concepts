Grad Cafe: Testing and Documentation
====================================

This application collects public graduate-admissions reports, preserves their
original fields, stores them in PostgreSQL, and presents eleven analyses.
Module 4 adds deterministic tests, an injectable Flask factory, and documentation
to the existing Module 3 application.

.. toctree::
   :maxdepth: 2
   :caption: Developer guide

   setup
   architecture
   api
   testing
   operations

Verification
------------

The local suite contains 101 passing tests and covers 100% of Python statements
under ``src/``, including the inherited model helper. Database tests use real
PostgreSQL. Website and model calls use fakes. This is line coverage, not a
claim that every possible input, browser interaction or model prediction has
been verified.

The repository's ``coverage_summary.txt`` contains the actual test report.
Remote CI success and documentation publication remain pending in
``README.md``. A local pass does not establish a successful GitHub run.

"""Build the eleven questions with SQLAlchemy instead of handwritten SQL.

An ORM maps a Python class (Applicant) to a database table.
Read query_data.py first to see the matching SQL for each question.
Run from module_4 with: python -m src.orm_queries
"""

from sqlalchemy import func, select

from sqlalchemy.orm import Session
from .models import Applicant
from .database import make_engine
from .query_data import print_results


def build_queries():
    """Return a dictionary: question number -> database query."""
    # These are database conditions, not True/False answers yet.
    # select chooses values; where chooses rows; func calls SQL functions.
    fall_2026 = Applicant.term.ilike("Fall 2026")
    accepted = Applicant.status.ilike("Accepted%")
    phd_degree = func.lower(func.replace(Applicant.degree, ".", "")) == "phd"

    computer_science_pattern = r"\m(computer\s+science|cs)\M"
    university_pattern = r"\m(georgetown|massachusetts institute of technology|mit|stanford|carnegie mellon|cmu)\M"
    original_computer_science = Applicant.program.regexp_match(computer_science_pattern, flags="i")
    original_university = Applicant.program.regexp_match(university_pattern, flags="i")
    llm_computer_science = Applicant.llm_generated_program.regexp_match(computer_science_pattern, flags="i")
    llm_university = Applicant.llm_generated_university.regexp_match(university_pattern, flags="i")

    queries = {}
    # Question 1: Count Fall 2026 entries.
    queries[1] = select(func.count()).select_from(Applicant).where(fall_2026)

    # Question 2: Percentage international. nullif prevents division by zero.
    international_count = func.count().filter(Applicant.us_or_international.ilike("International"))
    queries[2] = select(100.0 * international_count / func.nullif(func.count(), 0)).where(
        func.lower(Applicant.us_or_international).in_(["american", "international", "other"])
    )

    # Question 3: Average the available scores.
    queries[3] = select(
        func.avg(Applicant.gpa), func.avg(Applicant.gre),
        func.avg(Applicant.gre_v), func.avg(Applicant.gre_aw),
    )

    # Question 4: Average GPA for American Fall 2026 applicants.
    queries[4] = select(func.avg(Applicant.gpa)).where(
        fall_2026, Applicant.us_or_international.ilike("American")
    )

    # Question 5: Percentage accepted for Fall 2025.
    accepted_count = func.count().filter(accepted)
    queries[5] = select(100.0 * accepted_count / func.nullif(func.count(), 0)).where(
        Applicant.term.ilike("Fall 2025")
    )

    # Question 6: Average GPA for accepted Fall 2026 applicants.
    queries[6] = select(func.avg(Applicant.gpa)).where(fall_2026, accepted)

    # Question 7: Johns Hopkins master's entries in Computer Science.
    queries[7] = select(func.count()).select_from(Applicant).where(
        original_computer_science,
        Applicant.program.regexp_match(r"\m(johns?\s+hopkins|jhu)\M", flags="i"),
        func.lower(Applicant.degree).in_([
            "masters", "master", "master's", "ms", "m.s.",
            "msc", "m.sc.", "ma", "m.a.", "meng", "m.eng.",
        ]),
    )

    # Question 8: CS PhD acceptances at the four requested universities.
    queries[8] = select(func.count()).select_from(Applicant).where(
        fall_2026, accepted, phd_degree, original_computer_science, original_university
    )

    # Question 9: Compare original names with model-generated names.
    # A small subquery names the two counts so we can subtract them.
    counts = select(
        func.count().filter(original_computer_science, original_university).label("original_count"),
        func.count().filter(llm_computer_science, llm_university).label("llm_count"),
    ).where(fall_2026, accepted, phd_degree).subquery()
    queries[9] = select(
        counts.c.original_count,
        counts.c.llm_count,
        counts.c.llm_count - counts.c.original_count,
    )

    # Question 10: Count entries by degree, including missing degrees.
    reported_degree = func.coalesce(Applicant.degree, "Unknown")
    queries[10] = select(reported_degree, func.count()).where(fall_2026).group_by(reported_degree).order_by(
        func.count().desc(), reported_degree
    )

    # Question 11: Compare GPA between acceptances and rejections.
    decision = func.lower(Applicant.status)
    queries[11] = select(
        decision, func.count(), func.count(Applicant.gpa), func.avg(Applicant.gpa)
    ).where(fall_2026, decision.in_(["accepted", "rejected"])).group_by(decision).order_by(decision)

    return queries


def run_orm_queries(database_url=None):
    """Use one consistent database snapshot, then close the connection."""
    results = {}
    engine = make_engine(database_url)
    try:
        with Session(engine) as session:
            session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
            for number, statement in build_queries().items():
                results[number] = session.execute(statement).all()
    finally:
        engine.dispose()
    return results


if __name__ == "__main__":
    print_results(run_orm_queries(), "MODULE 4 - SQLALCHEMY ORM RESULTS",
                  numbers=[1, 4, 5, 8, 9, 10])

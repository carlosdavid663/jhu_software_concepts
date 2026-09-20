
from sqlalchemy import func, select

from models import Applicant, Session
from query_data import print_results


def build_queries():

    fall_2026 = Applicant.term.ilike("Fall 2026")
    accepted = Applicant.status.ilike("Accepted%")
    phd = func.lower(func.replace(Applicant.degree, ".", "")) == "phd"

    cs_pattern = r"\m(computer\s+science|cs)\M"
    school_pattern = r"\m(georgetown|massachusetts institute of technology|mit|stanford|carnegie mellon|cmu)\M"
    original_cs = Applicant.program.regexp_match(cs_pattern, flags="i")
    original_school = Applicant.program.regexp_match(school_pattern, flags="i")
    llm_cs = Applicant.llm_generated_program.regexp_match(cs_pattern, flags="i")
    llm_school = Applicant.llm_generated_university.regexp_match(school_pattern, flags="i")

    queries = {}
    queries[1] = select(func.count()).select_from(Applicant).where(fall_2026)

    international_count = func.count().filter(Applicant.us_or_international.ilike("International"))
    queries[2] = select(100.0 * international_count / func.nullif(func.count(), 0)).where(
        func.lower(Applicant.us_or_international).in_(["american", "international", "other"])
    )

    queries[3] = select(
        func.avg(Applicant.gpa), func.avg(Applicant.gre),
        func.avg(Applicant.gre_v), func.avg(Applicant.gre_aw),
    )

    queries[4] = select(func.avg(Applicant.gpa)).where(
        fall_2026, Applicant.us_or_international.ilike("American")
    )

    accepted_count = func.count().filter(accepted)
    queries[5] = select(100.0 * accepted_count / func.nullif(func.count(), 0)).where(
        Applicant.term.ilike("Fall 2025")
    )

    queries[6] = select(func.avg(Applicant.gpa)).where(fall_2026, accepted)

    queries[7] = select(func.count()).select_from(Applicant).where(
        original_cs,
        Applicant.program.regexp_match(r"\m(johns?\s+hopkins|jhu)\M", flags="i"),
        func.lower(Applicant.degree).in_([
            "masters", "master", "master's", "ms", "m.s.",
            "msc", "m.sc.", "ma", "m.a.", "meng", "m.eng.",
        ]),
    )

    queries[8] = select(func.count()).select_from(Applicant).where(
        fall_2026, accepted, phd, original_cs, original_school
    )

    # A small subquery names the two counts so we can subtract them.
    counts = select(
        func.count().filter(original_cs, original_school).label("original_count"),
        func.count().filter(llm_cs, llm_school).label("llm_count"),
    ).where(fall_2026, accepted, phd).subquery()
    queries[9] = select(
        counts.c.original_count,
        counts.c.llm_count,
        counts.c.llm_count - counts.c.original_count,
    )

    degree = func.coalesce(Applicant.degree, "Unknown")
    queries[10] = select(degree, func.count()).where(fall_2026).group_by(degree).order_by(
        func.count().desc(), degree
    )

    decision = func.lower(Applicant.status)
    queries[11] = select(
        decision, func.count(), func.count(Applicant.gpa), func.avg(Applicant.gpa)
    ).where(fall_2026, decision.in_(["accepted", "rejected"])).group_by(decision).order_by(decision)

    return queries


def run_orm_queries():
    """Use one consistent database snapshot, then close the connection."""
    results = {}
    with Session() as session:
        session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        for number, statement in build_queries().items():
            results[number] = session.execute(statement).all()
    return results


if __name__ == "__main__":
    print_results(run_orm_queries(), "MODULE 3 - SQLALCHEMY ORM RESULTS",
                  numbers=[1, 4, 5, 8, 9, 10])

"""SQLAlchemy's Python description of the existing applicants table."""

from sqlalchemy import Date, Float, Integer, Text
from sqlalchemy.orm import DeclarativeBase, mapped_column

class Base(DeclarativeBase):
    """SQLAlchemy needs a shared base class for its table descriptions."""
    pass


class Applicant(Base):
    """Describe one database row. Each mapped_column names a table column."""
    __tablename__ = "applicants"

    # The primary key identifies a row. A URL must also be unique and present.
    p_id = mapped_column(Integer, primary_key=True)
    program = mapped_column(Text)
    comments = mapped_column(Text)
    date_added = mapped_column(Date)
    url = mapped_column(Text, unique=True, nullable=False)
    status = mapped_column(Text)
    term = mapped_column(Text)
    us_or_international = mapped_column(Text)
    gpa = mapped_column(Float)
    gre = mapped_column(Float)
    gre_v = mapped_column(Float)
    gre_aw = mapped_column(Float)
    degree = mapped_column(Text)
    llm_generated_program = mapped_column(Text)
    llm_generated_university = mapped_column(Text)

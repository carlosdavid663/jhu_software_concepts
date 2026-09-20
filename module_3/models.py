"""SQLAlchemy's Python description of the existing applicants table."""

from sqlalchemy import Date, Float, Integer, Text, URL, create_engine
from sqlalchemy.orm import DeclarativeBase, mapped_column, sessionmaker

from database import database_settings

settings = database_settings()
database_url = URL.create(
    "postgresql+psycopg",
    username=settings["user"],
    password=settings["password"],
    host=settings["host"],
    port=settings["port"],
    database=settings["dbname"],
)
engine = create_engine(database_url, connect_args={"connect_timeout": 5})
Session = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class Applicant(Base):
    __tablename__ = "applicants"

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

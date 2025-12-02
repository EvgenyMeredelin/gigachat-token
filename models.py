from sqlalchemy import Integer, MetaData, Text
from sqlalchemy.orm import declarative_base, mapped_column


Base = declarative_base(metadata=MetaData(schema="gigachat"))


class TokenReleaseRecord(Base):
    """Token release database record. """

    __tablename__ = "token_release"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    dateReleased = mapped_column(Text, nullable=False)
    dateExpires = mapped_column(Text, nullable=False)
    minutesValid = mapped_column(Integer, nullable=False)
    host = mapped_column(Text, nullable=False)
    username = mapped_column(Text, nullable=False)

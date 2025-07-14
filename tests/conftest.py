import pytest
import pytest_postgresql
import sqlalchemy as sqla
from src.schema import Base

db_fixture = pytest_postgresql.factories.postgresql(
    process_fixture_name="postgresql_proc", dbname="decision_tracker"
)


@pytest.fixture
def db_engine(db_fixture) -> sqla.Engine:
    db_engine = sqla.create_engine(
        sqla.URL.create(
            drivername="postgresql",
            username=db_fixture.info.user,
            password="password-not-needed",
            host=db_fixture.info.host,
            port=db_fixture.info.port,
            database=db_fixture.info.dbname,
        )
    )
    Base.metadata.create_all(db_engine)
    return db_engine

import sqlalchemy as sqla

from expressions import And


def test_demo(db_engine: sqla.Engine) -> None:
    y = And(a=True, b=True).with_name("y")
    y.to_db(db_engine)
    db_engine

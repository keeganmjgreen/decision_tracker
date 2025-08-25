# https://app.codeimage.dev/

import datetime as dt

from decisiontracker import Int
from sqlalchemy import Engine

my_sum = Int(a=1).plus(b=2).with_name("my_sum")

my_comparison = my_sum.times(c=3).geq(
    Int(d=4).minus(Int(1).divided_by(f=5))
).with_name("my_comparison")

output = my_comparison.or_(g=False).and_(h=True).with_name("output")

with Engine(url=...).connect() as conn:
    output.to_db(conn, metadata=dict(timestamp=dt.UTC))

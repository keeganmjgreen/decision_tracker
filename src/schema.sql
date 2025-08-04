CREATE TYPE operator AS ENUM (
    'and',
    'not',
    'or',
);

CREATE TABLE evaluated_expression (
    id UUID PRIMARY KEY,
    parent_id UUID,
    name VARCHAR NULL,
    value JSONB,
    operator operator NOT NULL

    CONSTRAINT FOREIGN KEY parent_id REFERENCES evaluated_expression(id)
);

CREATE TABLE evaluated_expression (
    id UUID PRIMARY KEY,
    name TEXT NULL,
    value JSONB,
    operator TEXT NOT NULL
);

CREATE TABLE evaluated_expression_association (
    child_id PRIMARY KEY UUID,
    parent_id PRIMARY KEY UUID,

    CONSTRAINT FOREIGN KEY child_id REFERENCES evaluated_expression.id,
    CONSTRAINT FOREIGN KEY parent_id REFERENCES evaluated_expression.id
);

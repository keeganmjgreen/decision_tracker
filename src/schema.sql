CREATE TABLE evaluated_expression (
    id UUID PRIMARY KEY,
    parent_id UUID,
    name TEXT NULL,
    value JSONB,
    operator TEXT NOT NULL

    CONSTRAINT FOREIGN KEY parent_id REFERENCES evaluated_expression(id)
);

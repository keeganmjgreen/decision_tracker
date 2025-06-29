CREATE TABLE evaluated_expression (
    id UUID PRIMARY KEY,
    name TEXT NULL,
    value JSONB NOT NULL,
    operator operator NOT NULL
);

CREATE TABLE operand (
    used_in_evaluated_expression_id UUID NOT NULL,
    value JSONB NOT NULL, -- evaluated_expression.id or raw literal
    CONSTRAINT FOREIGN KEY used_in_evaluated_expression_id REFERENCES evaluated_expression(id)
);

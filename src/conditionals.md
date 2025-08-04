```mermaid
graph LR
    BaseExpression --if_--> IncompleteConditional
    IncompleteConditional --else_--> Conditional
```

```mermaid
graph LR
    If --then--> IncompleteConditional
    IncompleteConditional --else_--> Conditional
    IncompleteConditional --elif_--> Elif
    Elif --then--> IncompleteConditional
```

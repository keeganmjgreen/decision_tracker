import DataTypes from 'sequelize';

function evaluatedExpressionRecord() {
    const operator = DataTypes.ENUM(
        'and',
        'or',
        'not',
    )
    const EvaluatedExpression = sequelize.define(
        'EvaluatedExpression',
        {
            id: {
                type: DataTypes.UUID,
                primaryKey: true,
                allowNull: False,
            },
            parentId: {
                type: DataTypes.UUID,
            },
            name: {
                type: DataTypes.STRING,
            },
            value: {
                type: DataTypes.JSONB,
            },
            operator: {
                type: operator,
            },
        },
    );
    EvaluatedExpression.belongsTo(
        EvaluatedExpression,
        { targetKey: 'id', foreignKey: 'parentId', as: 'parent' },
    );
    EvaluatedExpression.hasMany(
        EvaluatedExpression,
        { targetKey: 'id', foreignKey: 'parentId', as: 'children' },
    );
    return EvaluatedExpression
}

export { evaluatedExpressionRecord };

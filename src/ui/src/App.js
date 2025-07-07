import { React, useState } from 'react';
import './styles.css'
// import EvaluatedExpression from './schema.js'

export const evaluatedExpressions = [
    {
        id: 0,
        name: 'y',
        value: true,
        operator: 'and',
        getChildren: function () {
            return [
                {
                    id: 1,
                    name: 'a',
                    value: true,
                    operator: null,
                    getChildren: function () { return [] },
                },
                {
                    id: 2,
                    name: 'b',
                    value: true,
                    operator: null,
                    getChildren: function () { return [] },
                },
            ]
        },
    },
]

function Expression({ evaluatedExpression }) {
    const [childrenVisible, setChildrenVisibility] = useState(true);

    let indentedDivs = []
    if (childrenVisible) {
        const children = evaluatedExpression.getChildren();
        if (children.length > 0) {
            indentedDivs.push(<div className="because">because</div>);
        }
        for (let i = 0; i < children.length; i++) {
            const child = children[i];
            indentedDivs.push(<Expression evaluatedExpression={child} />);
            if (i < children.length - 1) {
                indentedDivs.push(<div className="operator">{evaluatedExpression.operator}</div>)
            }
        }
    }
    return (
        <div>
            <div className="expression">{evaluatedExpression.name} := {`${evaluatedExpression.value}`}</div>
            <div className="indented">{indentedDivs}</div>
        </div>
    );
}

function App() {
    // const evaluatedExpressions = await evaluatedExpressions.findAll()
    const expressions = evaluatedExpressions.map(ee => <Expression evaluatedExpression={ee} key={ee.id} />);
    return <div>{expressions}</div>;
}

export default App;

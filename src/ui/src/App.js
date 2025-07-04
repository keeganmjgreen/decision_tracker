import React, { Component } from 'react';
import Tree, { renderers } from 'react-virtualized-tree';
import './styles.css'

export const NODES = [
    {
        id: 0,
        name: 'y := True',
        children: [
            {
                id: 2,
                name: 'because (a := True)',
            },
            {
                id: 5,
                name: 'and (b := True)',
            },
        ],
    },
]

class App extends Component {
    state = {
        nodes: NODES,
    };

    handleChange = nodes => {
        this.setState({ nodes });
    };

    render() {
        return (
            <div>
                <div class="expression">y := True</div>
                <div class="indented">
                    <div class="because">because</div>
                    <div class="expression">a := True</div>
                    <div class="operator">and</div>
                    <div class="expression">b := True</div>
                </div>
            </div>
        );
    }
}


export default App;

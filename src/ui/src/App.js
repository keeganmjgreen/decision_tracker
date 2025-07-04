import React, { Component } from 'react';
import Tree, { renderers } from 'react-virtualized-tree';

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
            <div style={{ height: 500 }}>
                <Tree nodes={this.state.nodes} onChange={this.handleChange}>
                    {({ style, node, ...rest }) => (
                        <div style={style}>
                            <renderers.Expandable node={node} {...rest}>
                                <code>{node.name}</code>
                            </renderers.Expandable>
                        </div>
                    )}
                </Tree>
            </div>
        );
    }
}


export default App;

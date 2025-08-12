import os
import sys
import json
import inspect
from pathlib import Path
from pyvis.network import Network

try:
    from .start_server import run_server_in_background, is_web_server_running
except ImportError:
    from start_server import run_server_in_background, is_web_server_running


def is_notebook():
    try:
        return get_ipython().__class__.__name__ == "ZMQInteractiveShell"
    except NameError:
        return False


def handle_server_start(
    output_file,
    start_server=True,
    port=8080,
    verbose=False,
):
    """Handle server startup or provide instructions."""
    if not start_server:
        return

    base_dir = os.path.expanduser("~")
    rel_path = os.path.relpath(output_file, base_dir).replace(os.sep, "/")
    url = f"http://localhost:{port}/{rel_path}"

    if not is_web_server_running(port):
        if is_notebook():
            server_module = sys.modules[run_server_in_background.__module__]
            print(
                f"[INFO]: Running in a Notebook, no server detected on port {port}.\n"
                f"Start the server manually with: python {os.path.abspath(server_module.__file__)} {port}\n"
                f"Then open: {url}\n"
            )
        else:
            run_server_in_background(port=port, directory=base_dir)
    else:
        if verbose:
            print(f"Your knowledge graph is available at: {url}")


def create_network(kg_data, height="900px", width="100%"):
    """Creates a Knowledge Graph Network"""

    net = Network(
        height=height,
        width=width,
        directed=False,
        notebook=True,
        cdn_resources="remote",
        # select_menu=True,
        # filter_menu=True,
        neighborhood_highlight=True,
        # bgcolor="#ffffff",
    )

    for node in kg_data["nodes"]:
        label = node["label"]
        if len(label) > 20:
            words = label.split()
            lines = []
            current_line = ""
            for word in words:
                if len(current_line + " " + word) > 20:
                    lines.append(current_line)
                    current_line = word
                else:
                    current_line = current_line + " " + word if current_line else word
            if current_line:
                lines.append(current_line)
            label = "\n".join(lines)

        net.add_node(
            node["id"],
            label=label,
            title=node["label"],  # Tooltip still shows full text
            shape="box",
            size=30,  # Larger nodes
            color={"background": "#97C2FC", "border": "#2B7CE9"},
            font={"size": 16, "color": "#000000"},
        )

    # Add edges
    for edge in kg_data["edges"]:
        net.add_edge(
            edge["from"],
            edge["to"],
            title=edge["relationship_description"],
            label=edge["relationship"],
            width=1,  # Thicker edges
            hoverWidth=0,  # no widening on hover
            selectionWidth=1.1,
            color={
                "color": "#64646445",  # normal edge color
                "highlight": "#2B7CE9",  # when selected
                # "hover": "#64646480",  # on mouse‑over
            },
            smooth={
                "type": "straightCross",  # Use straight lines
                "roundness": 0.5,  # Control curvature (0 = straight)
            },
            arrows={
                "to": {
                    "enabled": True,  # Add arrow at target
                    "scaleFactor": 0.3,  # Size of the arrow
                }
            },
        )

    net.options.physics.enabled = True
    # net.options.physics.solver = "hierarchicalRepulsion"

    # Additional options can be set this way too
    net.options.physics.barnesHut = {
        "gravitationalConstant": -2000,
        "centralGravity": 0.1,
        "springLength": 200,
        "springConstant": 0.04,
    }
    # net.options.physics.barnesHut = {
    #     "gravitationalConstant": -13200,
    #     "centralGravity": 0.1,
    #     "springLength": 135,
    #     "springConstant": 0.015,
    # }
    # net.options.physics.hierarchicalRepulsion = {
    #     "centralGravity": 0,
    #     "springLength": 140,
    #     "springConstant": 0,
    #     "nodeDistance": 165,
    #     "avoidOverlap": 0.66,
    # }

    # Show buttons for physics control
    net.show_buttons(filter_=["physics", "clustering"])

    return net


def save_html(net, html_path):

    html = net.generate_html()
    search_widget = (
        r"""
        <style>
        /* Container positioning stays the same */
        #searchContainer {
            position: absolute;
            top: 10px;
            left: 10px;
            z-index: 1000;
            font-family: Arial, sans-serif;
        }

        /* The input itself */
        #nodeSearch {
            width: 420px;
            padding: 10px 16px;
            font-size: 16px;
            border: 1px solid #dfe1e5;
            border-radius: 12px;
            box-shadow: 0 1px 6px rgba(32,33,36,0.28);
            transition: box-shadow 0.2s, border-color 0.2s;
            outline: none;
        }
        #nodeSearch:focus {
            box-shadow: 0 4px 8px rgba(32,33,36,0.3);
        }
        #nodeSearch::placeholder {
            color: #9aa0a6;
        }

        /* The dropdown */
        #searchResults {
            margin-top: 4px;
            width: 420px;
            max-height: 260px;
            overflow-y: auto;
            background: #fff;
            border: None;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(32,33,36,0.28);
            list-style: none;
            padding: 0;
        }
        #searchResults li {
            padding: 10px 16px;
            cursor: pointer;
            transition: background 0.1s;
        }
        #searchResults li:hover {
            background: #f1f3f4;
        }
        /* Info box styling */
        #infoBox {
            position: absolute;
            top: 10px;
            right: 10px;
            background-color: rgba(255, 255, 255, 0.9);
            border: 1px solid #dfe1e5;
            border-radius: 8px;
            padding: 8px 12px;
            font-family: Arial, sans-serif;
            font-size: 16px;
            color: #5f6368;
            box-shadow: 0 1px 6px rgba(32,33,36,0.28);
            z-index: 1000;
        }
        #infoBox code {
            font-family: 'Courier New', monospace;
            background-color: #f1f3f4;
            padding: 2px 4px;
            border-radius: 3px;
        }
        </style>


    <div id="searchContainer">
        <input type="text" id="nodeSearch" placeholder="🔎 Find node…"/>
        <ul id="searchResults"></ul>
    </div>

     <div id="infoBox">
        filename: <code>"""
        + html_path
        + """</code>
    </div>
    """.format(
            html_path
        )
    )

    html = html.replace('<div id="mynetwork"', search_widget + '\n<div id="mynetwork"')

    injection = r"""
    <script>
        window.addEventListener('load', function() {
        const container = document.getElementById('searchContainer');
        const input     = document.getElementById('nodeSearch');
        const results   = document.getElementById('searchResults');

        function refreshResults() {
            const term    = input.value.toLowerCase();
            const all     = network.body.data.nodes.get();
            const matches = all.filter(n => n.title.toLowerCase().includes(term));

            // just select, don't focus/zoom
            network.selectNodes(matches.map(n => n.id));

            results.innerHTML = '';
            matches.slice(0,50).forEach(n => {
            const li = document.createElement('li');
            li.textContent = `${n.title} (${n.id})`;
            li.onclick = () => {
                network.selectNodes([n.id]);
                // highlight neighbors without zoom
                neighbourhoodHighlight({ nodes: [n.id] });
                results.innerHTML = '';
            };
            results.appendChild(li);
            });
        }

        input.addEventListener('keyup', refreshResults);
        input.addEventListener('focus', function() {
            if (input.value.trim()) refreshResults();
        });
        document.addEventListener('click', function(e) {
            if (!container.contains(e.target)) results.innerHTML = '';
        });
        });



    // Add collapsible physics controller
    document.addEventListener('DOMContentLoaded', function() {
    setTimeout(function() {
        if (typeof network !== 'undefined') {
        // Create the controller container
        const physicsControl = document.createElement('div');
        physicsControl.id = 'physicsControl';
        physicsControl.innerHTML = `
            <div id="physicsHeader">
            <h3>Physics Settings</h3>
            <button id="collapseButton">−</button>
            </div>
            <div id="physicsContent">
            <div class="control-group">
                <label for="gravity">Gravity Strength:</label>
                <input type="range" id="gravity" min="-10000" max="-500" value="-2000" step="100">
                <span id="gravityValue">-2000</span>
            </div>
            <div class="control-group">
                <label for="centralGravity">Central Gravity:</label>
                <input type="range" id="centralGravity" min="0.01" max="1" value="0.1" step="0.01">
                <span id="centralGravityValue">0.1</span>
            </div>
            <div class="control-group">
                <label for="springLength">Spring Length:</label>
                <input type="range" id="springLength" min="50" max="500" value="200" step="10">
                <span id="springLengthValue">200</span>
            </div>
            <div class="control-group">
                <label for="springConstant">Spring Constant:</label>
                <input type="range" id="springConstant" min="0.01" max="0.5" value="0.04" step="0.01">
                <span id="springConstantValue">0.04</span>
            </div>
            <div class="control-group">
                <button id="physicsToggle">Physics: ON</button>
                <button id="resetPhysics">Reset</button>
            </div>
            </div>
        `;
        
        // Add the controller to the DOM
        document.body.appendChild(physicsControl);
        
        // Add style tag for the controller
        const style = document.createElement('style');
        style.textContent = `
            #physicsControl {
            position: absolute;
            bottom: 20px;
            left: 20px;
            width: 280px;
            background-color: rgba(255, 255, 255, 0.95);
            border: 1px solid #dfe1e5;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(32,33,36,0.28);
            z-index: 1000;
            overflow: hidden;
            font-family: Arial, sans-serif;
            transition: height 0.3s ease;
            }
            
            #physicsHeader {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 12px;
            background-color: #f8f9fa;
            border-bottom: 1px solid #dfe1e5;
            cursor: pointer;
            }
            
            #physicsHeader h3 {
            margin: 0;
            font-size: 16px;
            color: #202124;
            }
            
            #collapseButton {
            background: none;
            border: none;
            font-size: 18px;
            cursor: pointer;
            color: #5f6368;
            padding: 0 5px;
            }
            
            #physicsContent {
            padding: 12px;
            transition: max-height 0.3s ease;
            overflow: hidden;
            }
            
            .control-group {
            margin-bottom: 10px;
            }
            
            .control-group label {
            display: block;
            margin-bottom: 5px;
            font-size: 14px;
            color: #5f6368;
            }
            
            .control-group input[type="range"] {
            width: 100%;
            margin-bottom: 5px;
            }
            
            .control-group span {
            font-size: 12px;
            color: #5f6368;
            float: right;
            }
            
            .control-group button {
            padding: 8px 12px;
            background-color: #f1f3f4;
            border: 1px solid #dadce0;
            border-radius: 4px;
            font-size: 14px;
            color: #202124;
            cursor: pointer;
            margin-right: 8px;
            }
            
            .control-group button:hover {
            background-color: #e8eaed;
            }
            
            #physicsControl.collapsed #physicsContent {
            display: none;
            }
        `;
        document.head.appendChild(style);
        
        // Implement controller functionality
        const collapseButton = document.getElementById('collapseButton');
        const physicsContent = document.getElementById('physicsContent');
        const physicsToggle = document.getElementById('physicsToggle');
        const resetPhysics = document.getElementById('resetPhysics');
        const gravitySlider = document.getElementById('gravity');
        const centralGravitySlider = document.getElementById('centralGravity');
        const springLengthSlider = document.getElementById('springLength');
        const springConstantSlider = document.getElementById('springConstant');
        const gravityValue = document.getElementById('gravityValue');
        const centralGravityValue = document.getElementById('centralGravityValue');
        const springLengthValue = document.getElementById('springLengthValue');
        const springConstantValue = document.getElementById('springConstantValue');
        
        // Initialize values from network settings
        if (network.physics && network.physics.options.barnesHut) {
            const options = network.physics.options.barnesHut;
            gravitySlider.value = options.gravitationalConstant;
            centralGravitySlider.value = options.centralGravity;
            springLengthSlider.value = options.springLength;
            springConstantSlider.value = options.springConstant;
            
            gravityValue.textContent = options.gravitationalConstant;
            centralGravityValue.textContent = options.centralGravity;
            springLengthValue.textContent = options.springLength;
            springConstantValue.textContent = options.springConstant;
        }
        
        // Toggle collapse
        let isCollapsed = true;
        physicsControl.classList.add('collapsed');
        collapseButton.textContent = '+';
        
        collapseButton.addEventListener('click', function() {
            isCollapsed = !isCollapsed;
            if (isCollapsed) {
            physicsControl.classList.add('collapsed');
            collapseButton.textContent = '+';
            } else {
            physicsControl.classList.remove('collapsed');
            collapseButton.textContent = '−';
            }
        });
        
        // Also allow clicking the header to toggle
        document.getElementById('physicsHeader').addEventListener('click', function(e) {
            // Only trigger if we didn't click the button directly
            if (e.target !== collapseButton) {
            collapseButton.click();
            }
        });
        
        // Toggle physics
        let physicsEnabled = true;
        physicsToggle.addEventListener('click', function() {
            physicsEnabled = !physicsEnabled;
            network.physics.enabled = physicsEnabled;
            
            if (physicsEnabled) {
            physicsToggle.textContent = 'Physics: ON';
            network.startSimulation();
            } else {
            physicsToggle.textContent = 'Physics: OFF';
            network.stopSimulation();
            }
        });
        
        // Reset physics
        resetPhysics.addEventListener('click', function() {
            gravitySlider.value = -2000;
            centralGravitySlider.value = 0.1;
            springLengthSlider.value = 200;
            springConstantSlider.value = 0.04;
            
            gravityValue.textContent = -2000;
            centralGravityValue.textContent = 0.1;
            springLengthValue.textContent = 200;
            springConstantValue.textContent = 0.04;
            
            network.physics.options.barnesHut = {
            gravitationalConstant: -2000,
            centralGravity: 0.1,
            springLength: 200,
            springConstant: 0.04
            };
            
            // Restart simulation
            if (physicsEnabled) {
            network.startSimulation();
            }
        });
        
        // Update physics on slider changes
        gravitySlider.addEventListener('input', function() {
            gravityValue.textContent = this.value;
            network.physics.options.barnesHut.gravitationalConstant = Number(this.value);
            if (physicsEnabled) network.startSimulation();
        });
        
        centralGravitySlider.addEventListener('input', function() {
            centralGravityValue.textContent = this.value;
            network.physics.options.barnesHut.centralGravity = Number(this.value);
            if (physicsEnabled) network.startSimulation();
        });
        
        springLengthSlider.addEventListener('input', function() {
            springLengthValue.textContent = this.value;
            network.physics.options.barnesHut.springLength = Number(this.value);
            if (physicsEnabled) network.startSimulation();
        });
        
        springConstantSlider.addEventListener('input', function() {
            springConstantValue.textContent = this.value;
            network.physics.options.barnesHut.springConstant = Number(this.value);
            if (physicsEnabled) network.startSimulation();
        });
        }
    }, 500);
    });
    
    </script>


    """
    html = html.replace("</body>", injection + "\n</body>")

    with open(html_path, "w", encoding="utf8") as f:
        f.write(html)


def save_json(kg_data: dict, json_path: str = None):
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(kg_data, jf, indent=2)


def setup_paths(output_file: str = None):

    if output_file is None:
        html_path = Path("tmp/knowledge_graph.html")
    else:
        html_path = Path(output_file)
        if html_path.suffix != ".html":
            html_path = html_path.with_suffix(".html")

    json_path = html_path.with_suffix(".json")
    html_path.parent.mkdir(parents=True, exist_ok=True)

    return str(html_path), str(json_path)


def plot_kg(
    kg_data,
    file_name=None,
    output_file=None,
    port=8086,
    start_server=True,
    verbose = False,
):
    if isinstance(kg_data, str):
        try:
            kg_data = json.loads(kg_data)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON string for kg_data.")

    html_path, json_path = setup_paths(output_file)

    net = create_network(kg_data)
    save_html(net, html_path)
    save_json(kg_data, json_path)

    # print(f"Knowledge graph saved to: {html_path}")
    handle_server_start(html_path, start_server, port, verbose)


if __name__ == "__main__":
    example_data = {
        "nodes": [
            {"id": 1, "label": "Concept A"},
            {"id": 2, "label": "Concept B"},
            {"id": 3, "label": "Concept C"},
        ],
        "edges": [
            {
                "from": 1,
                "to": 2,
                "relationship": "relates to",
                "relationship_description": "Concept A relates to Concept B",
            },
            {
                "from": 2,
                "to": 3,
                "relationship": "depends on",
                "relationship_description": "Concept B depends on Concept C",
            },
        ],
    }
    assets_dir = Path(__file__).resolve().parents[2]
    example_data = json.loads(
        (assets_dir / "assets/kg/LDA.json").read_text(encoding="utf-8")
    )
    plot_kg(example_data)

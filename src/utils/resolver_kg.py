import json
from pipeline.apollo.src.utils.logger import setup_logging, get_logger

from pipeline.apollo.src import LLM

setup_logging()
logger = get_logger(__name__)

# disable logger prints
logger.disabled = True


def fixing_agent(kg_dict):
    lm = LLM("gpt-4o-mini")
    prompt = f"""

    The following dict is intended to be a pure JSON, but has errors (comments, trailing commas, bad quotes, etc).
    Please strip comments and other invalid bits and return _only_ the corrected JSON object. 

    Provided JSON object:
    {kg_dict}
    
    Output: 
    - Adhere to the provided JSON format strictly and do not add any additional text.
    """
    formated_prompt = prompt.format(kg_dict=kg_dict)
    fixed_kg = lm(formated_prompt)[0]

    print("Attempting to fix the JSON with LLM...")
    print("\nInput JSON:")
    print(kg_dict)
    print("\nPrompt:")
    print(formated_prompt)
    print("\nLLM response:")
    print(fixed_kg)

    return fixed_kg


def validate_knowledge_graph(kg_text):
    """Ensures all nodes referenced in edges actually exist in the nodes list."""
    parsed_kg = None
    last_err = None

    # --- Attempt 1: direct parse ---
    try:
        parsed_kg = json.loads(kg_text)
    except json.JSONDecodeError as e:
        print(f"JSON Decode Error: {e}")
        last_err = e
        logger.info(f"Direct parse failed: {e}")
        start = max(0, e.pos - 100)
        end = min(len(kg_text), e.pos + 100)
        context = kg_text[start:end]

        print(f"JSON context around error (pos {e.pos}):")
        print(f"...{context}...")

        position_marker = " " * (min(100, e.pos - start)) + "^"
        print(f"   {position_marker}")

    # --- Attempt 2: manual hacks ---
    if parsed_kg is None:
        try:
            fixed = kg_text
            if '"""' in fixed:
                fixed = fixed.replace('"""', '"')
                logger.info("Applied triple-quote replacement")
            if "```json" in fixed or "```" in fixed:
                fixed = fixed.replace("```json", "").replace("```", "")
                logger.info("Removed markdown code fences")
            parsed_kg = json.loads(fixed)
        except Exception as e:
            last_err = e
            logger.info("Manual fixes failed to parse JSON")

    # --- Attempts 3 & 4: LLM cleanup ---
    attempts = 0
    while parsed_kg is None and attempts < 2:
        attempts += 1
        try:
            cleaned = fixing_agent(kg_text)
            parsed_kg = json.loads(cleaned)
            logger.info(f"LLM cleaning succeeded on attempt {attempts}")
        except Exception as e:
            last_err = e
            logger.info(f"LLM cleaning attempt {attempts} failed: {e}")

    # --- Give up: fallback to empty graph ---
    if parsed_kg is None:
        logger.warning(
            "All JSON parsing attempts failed. "
            "Proceeding with an empty graph to avoid interrupting execution."
        )
        parsed_kg = {"nodes": [], "edges": []}

    node_ids = {node["id"] for node in parsed_kg["nodes"]}
    invalid_edges = []

    for i, edge in enumerate(parsed_kg["edges"]):
        if edge["from"] not in node_ids:
            logger.info(
                f"Warning: Edge {i} references non-existent 'from' node: {edge['from']}"
            )
            invalid_edges.append(i)
        elif edge["to"] not in node_ids:
            logger.info(
                f"Warning: Edge {i} references non-existent 'to' node: {edge['to']}"
            )
            invalid_edges.append(i)

    for i in sorted(invalid_edges, reverse=True):
        logger.info(f"Removing invalid edge: {parsed_kg['edges'][i]}")
        parsed_kg["edges"].pop(i)

    return json.dumps(parsed_kg, indent=2)


from collections import defaultdict


def extract_groups(data):

    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON string for kg_data.")

    edges = data["edges"]

    # Step 1: Group edges by (from, relationship)
    group_map = defaultdict(list)
    for edge in edges:
        key = (edge["from"], edge["relationship"])
        group_map[key].append(
            {
                "node_id": edge["to"],
                "relationship_description": edge.get("relationship_description", ""),
            }
        )

    # Step 2: Only keep groups with more than one child
    result = {}
    group_id = 1
    for (parent, rel), children in group_map.items():
        if len(children) > 1:
            result[f"group{group_id}"] = {
                "parent_node": parent,
                "relation": rel,
                "children_nodes": children,
            }
            group_id += 1

    return result

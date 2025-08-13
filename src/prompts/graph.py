PROMPTS = {}
EXAMPLES = {}

##################################################
#                  GEN KG PROMPT
##################################################

PROMPTS[
    "gen_kg_prompt_v7"
] = """
You are a top-tier algorithm designed for extracting information in structured formats to build a knowledge graph about {topic}.


# Instructions
Adhere to the following steps:

// Question Exploration
0. Based on the snippet provided formulate a set of questions that can expand our knowledge about the topic. 


// Entity Extraction
1. Identify all relevant entities to fully understand the provided snippet. For each identified entity, extract the following information:
- entity_name: Full name of the entity. An entity in a knowledge graph is a node that represents a real-world object, concept, or abstract idea, which can be uniquely identified.
- entity_description: short description of the entity and why is important to analyze it in this context to understand the snippet. 


// Relationship Extraction
2. From the entities identified in step 1, identify all pairs of (source_entity, target_entity) that are *clearly related* to each other.
For each pair of related entities, extract the following information:
- source_node_id: the node_id of the source entity, as identified in step 1
- target_node_id: the node_id of the target entity, as identified in step 1
- relationship_type: a short description (lower-case with underscores & between 1-4 words) why the two entities related to each other.
- relationship_description: explanation as to why you think the source entity and the target entity are related to each other
- To construct the entity related pairs use the description that we found in step 1.

// Key Words
3. Identify high-level key words that summarize the main concepts, themes, or topics of the entire text. These should capture the overarching ideas present in the document.

// Consideration:
- Do not invent entities or relations not directly stated.

# Output: 
- Do not return any additional information other than the JSON format below:
{{  
  "nodes": [
    {{
      "id": "entity_name",
      "label": "Human readable name",
      "description": "entity_description"
    }},
    {{
      "id": "project_apollo",
      "label": "Project Apollo",
      "description": "entity_description"
    }},
    {{
      "id": "nasa",
      "label": "NASA",
      "description": "entity_description"
    }},
    ...
  ],
  
  "edges": [
    {{
      "from": "source_node_id", 
      "to": "target_node_id", 
      "relationship": "relationship_type",
      "relationship_description": "relationship_description"
    }},
    {{
      "from": "project_apollo", 
      "to": "nasa", 
      "relationship": "lead_by", 
      "relationship_description": "relationship_description"
    }},
    ...
  ],
  
  "keywords": [
    {{
        "keyword1",
        "keyword2",
        ...
    }}
  ],

  "questions": [
    "question1",
    "question2",
    ...
  ],
}}


"""

##################################################
#            BUILD HIERARCHY KNOWLEDGE GRAPH
##################################################


PROMPTS[
    "build_hierarchy_kg_prompt_v8"
] = """

You are an expert KG-builder that can group sibling nodes under a new intermediary (“unifying”) node when they share the same relation to a parent.

Input:
- “kg”: a JSON knowledge graph with nodes and edges.
- “kg_group”: one or more groups, each specifying:
   • parent_node: the shared parent node ID  
   • relation: the edge label that all children share  
   • children_nodes: a list of { node_id, relationship_description } entries

Task:
1. For each group in kg_group:
   a. Verify that every children_node in the group has an edge from parent_node labeled exactly as relation, and that its relationship_description matches.  
   b. If all children qualify, create a new “unifying_node” with:
      - id: a unique identifier 
      - label: a concise human-readable name 
      - description: a summary of what those children have in common 
   c. Replace each original edge (parent → child) with two edges:
      1. parent_node → unifying_node, 
          a. relation: a short, meaningful relationship (lower-case with underscores & between 1-4 words)
          b. relationship_description: a short, meaningful relationship summarizing what those N children have in common.
      2. unifying_node → child_node, 
          a. relation: retaining the original relation from parent to child
          a. relationship_description: retaining the original relationship_description from parent to child
2. Leave all other nodes and edges unchanged.

Output:
Adhere to the JSON scheme of the provided by the input 'kg'.
"""


##################################################
#            MERGE KNOWLEDGE GRAPH
##################################################

PROMPTS[
    "merge_kg_prompt_v1"
] = """
You are a top-tier algorithm designed for merging information in structured format to build a knowledge graph about {topic}.


# Instructions
Adhere to the following steps:

// Merging Subgraphs
Merge the graphs into one

# Output: 
- Do not return any additional information other than the JSON format below:
{{  
  "nodes": [
    {{
      "id": "entity_name",
      "label": "Human readable name",
      "description": "entity_description"
    }},
    {{
      "id": "project_apollo",
      "label": "Project Apollo",
      "description": "entity_description"
    }},
    {{
      "id": "nasa",
      "label": "NASA",
      "description": "entity_description"
    }},
    ...
  ],
  
  "edges": [
    {{
      "from": "source_node_id", 
      "to": "target_node_id", 
      "relationship": "relationship_type",
      "relationship_description": "relationship_description"
    }},
    {{
      "from": "project_apollo", 
      "to": "nasa", 
      "relationship": "lead_by", 
      "relationship_description": "relationship_description"
    }},
    ...
  ],
  
}}

"""


##################################################
#            CLUSTERS KNOWLEDGE GRAPH
##################################################


PROMPTS[
    "cluster_entities_prompt_v4"
] = """" 

You are a helpful assistant that helps in normalizing entities for a knowledge graph.
Provided is a list of nodes from a knowledge graph (KG) and a set of clusters which represents entities that have been grouped together because they represent the same entity.

Your task is to update the clusters set by identifying from the set of nodes of the KG, which node should be place in the cluster.

Instructions:
Form clusters of nodes based on the following rules:
1. Exact-ID merge (Highest priority)  
   - If two nodes share the same `"id"`, place them in the same cluster.

2. String-normalization check (Secondary)  
   - For labels, perform the following normalization before comparison:  
     - lowercase  
     - Consider words that could have an identical British vs American spelling (e.g. "color" ↔ "colour" they are the same).  
   - If two normalized labels match, cluster them.

The provided clusters:
{clusters}


Output:
- Return the updated clusters with the same format as the input clusters.
{{
    "clusters": [
        {{
            "canonical_label": "...",
            "members": [
                {{
                    "id": "...",
                    "label": "..."
                }},
                ...
                {{
                    "id": "...",
                    "label": "..."
                }}
            ]
        }},
        ...
    ]
}}
"""


##################################################
#            EXPAND KNOWLEDGE GRAPH
##################################################

PROMPTS[
    "expand_kg_prompt_v7"
] = """
You are a helpful assistant working for a research team on expanding the provided knowledge graph. Your task is to come up with queries to deepen (depth) and expand (breadth) our understanding of the topic: {topic}.

Instructions:
1. Analyze the knowledge graph carefully to identify gaps in our understanding
2. Look for areas that are under-explored or completely missing
3. Consider aspects that would provide new perspectives not currently represented

Considerations: 
- IMPORTANT: The knowledge graph represents our accumulated knowledge so far - focus on what's MISSING, not what's already there
- Examine both nodes and relationships to find areas needing exploration
- Consider formulating queries that explore:
  - General queries: Areas entirely absent from the graph that could broaden understanding
  - In-depth queries: Existing areas that need deeper investigation
- Analyze which of these two types (general vs in-depth) would be more valuable at this stage
- For each query, provide one sentence explaining why this information would specifically fill a gap in the current knowledge graph

Constraints:
- Do NOT repeat any of the questions below as we have already explored them:
{questions_seen}

Output:
Adhere to the following format and do not output anything else:
{{
  "general_queries": [
    {{
      "query1": "General Query 1",
      "explanation1": "This addresses [specific gap] not currently represented in the graph"
    }},
    ...
  ],
  "in_depth_queries": [
    {{
      "query1": "In-depth Query 1",
      "explanation1": "This expands on [specific node/relationship] which is currently superficial"
    }},
    ...
  ]
}}
"""

##################################################
#            REFLECTION QUESTIONS-TO-QUERIES
##################################################


PROMPTS[
    "questions_to_queries_prompt_v3"
] = """
You are an expert researcher on the topic: {topic}. Your task is to transform the provided questions into effective search queries to expand our breath and depth of the topic treated.

Instructions:
- Think from the perspective of {audience}.
- Convert the `general_queries` and `in_depth_queries` into precise search terms for a search engine
- Create search queries that will provide the most valuable NEW information
- Focus on generating DIVERSE queries that cover different aspects of the topic
- Format each query as concise keywords (2-5 words) suitable for a search engine
- Rank the queries by importance, with the most critical knowledge gaps first

Constraints:
- Do not add include the '{topic}` in your search queries.
- Create search queries that MUST NOT repeat or paraphrase any query from the `queries_seen` provided below.  
- Avoid any two queries that share more than one keyword in common.
- Avoid creating queries that are likely to retrieve the same information.
- CRITICAL: Do NOT generate queries similar to any of the queries below:
{queries_seen}


Output:
- Adhere to the following format and do not add any other text:
{{
    "combined_queries": [
        "query_1",
        "query_2",
        ...
        "query_N"
    ]
}}
"""

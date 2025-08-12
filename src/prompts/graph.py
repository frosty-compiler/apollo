PROMPTS = {}
EXAMPLES = {}

##################################################
#               TRIPLET EXTRACTION
##################################################

PROMPTS[
    "extract_triplets_v0"
] = """
You are an expert in knowledge graph construction. Given a document, extract a structured knowledge graph with nodes and directed relationships.

- The graph should capture key concepts (nodes) and their relations (edges) as they appear in the document.
- Relations must be semantic and useful for understanding the topic in depth.
- Output the graph in triplet format: (subject, relation, object).
- For each triplet, make sure that:
- Nodes are consistent and not repeated under different names (e.g., “AI” vs “Artificial Intelligence”).
- Relations are concise and specific (e.g., “enables”, “causes”, “is part of”, “applies to”).
- Only include triplets relevant to the central topic: {topic}
- Add a short natural-language explanation for each triplet.

⸻

Document:
{snippet}

⸻

Output Format:

{{
  "topic": "{topic}",
  "triplets": [
    {{
      "subject": "X",
      "relation": "Y",
      "object": "Z",
      "explanation": "Explain why or how this relation exists."
    }},
    ...
  ]
}}
"""

##################################################
#               GEN_TRIPLETS_CHUNK
##################################################

PROMPTS[
    "gen_triplets_chunk_v0"
] = """
You are a skillfull PhD student which wants to understands about the following topic:

Topic: {topic}

Instructions:
- Based on the provided questions and document, your job is to extract uestions that will allows us to understand what is {topic}.
- Only generate questions that can be answer with the provided document.

Document:
'''
{snippet}
'''

Questions:
'''
{questions}
'''

Output:
- Provide your answer in the following format and nothing else:
1. Question 1
2. Question 2
3. ...
"""

##################################################
#               GEN_QUERIES_CHUNK
##################################################

PROMPTS[
    "gen_queries_chunk_v0"
] = """
You are a skillfull PhD student which wants to understands about the following topic:

Topic: {topic}

Instructions:
- Based on the provided document, generate questions that will allows us to understand what is {topic}.
- Only generate questions that can be answer with the provided document.

Document:
'''
{snippet}
'''

Output:
- Provide your answer in the following format and nothing else:
1. Question 1
2. Question 2
3. ...
"""

##################################################
#            GENERATE KNOWLEDGE GRAPH
##################################################

PROMPTS[
    "gen_kg_from_chunk_v0"
] = """
Based on the following snippet construct a Knowledge Graph about the following topic.

Topic: {topic}

Instructions:
- Extract the most relevant entities and relationships from the snippet.
- Use the extracted entities to create nodes in the graph.
- Use the extracted relationships to create edges between the nodes.
- Provide the KB in the following JSON format and do not include any additional text or explanation:

{{
  "nodes": [
    {{"id": "node_id", "label": "node_label"}},
    ...
  ],
  "edges": [
    {{"from": "source_node_id", "to": "target_node_id", "relationship": "relationship_type"}},
    ...
  ]
}}


Snippet:
{snippet}
"""


##################################################
#                  GEN KG PROMPT
##################################################


PROMPTS[
    "gen_kg_prompt_v1"
] = """
Based on the following snippet construct a Knowledge Graph about the provided topic.

Instructions:
- Extract the most relevant entities and relationships from the snippet.
- Extract as many entities and relationships as possible.
- Use the extracted entities to create nodes in the graph.
- Use the extracted relationships to create edges between the nodes.
- The snippets provided are extracted from scientific papers and might contain references or heading numbers, they should be ignored.
- Use the topic as the root node of the graph.
- Provide the KB in the following JSON format and do not include any additional text or explanation:

{{
"nodes": [
    {{"id": "node_id", "label": "node_label"}},
    ...
],
"edges": [
    {{"from": "source_node_id", "to": "target_node_id", "relationship": "relationship_type"}},
    ...
]
}}
"""


PROMPTS[
    "gen_kg_prompt_v2"
] = """
Based on the provided snippet, construct a Knowledge Graph about {topic} which.

Instructions:
- First reason whether the snippet is relevant to explain the topic {topic}. If it is not relevant, return an empty graph. It can happen that the snippet is describing a figure or table which in this case might not be relevant.
- Extract ONLY entities and relationships that are directly relevant to {topic} and which can create a mindmap for a person that is trying to understand the topic.
- Normalize entity names (e.g., "machine learning" and "ML" should be the same entity)
- Assign clear, consistent relationship types (e.g., "causes", "improves", "contains", "requires")
- Use concise but descriptive node labels (typically 1-5 words)
- Ignore citations, references, section numbers, and other document metadata
- Limit entities to those that appear at least twice in the text or are clearly significant
- Use {topic} as the root node of the graph

Output the KB in the following JSON format without any additional text or explanation:

    {{
    "nodes": [
        {{"id": "0", "label": "node_label_1"}},
        {{"id": "1", "label": "node_label_2"}},
        ...
    ],
    "edges": [
        {{"from": "source_node_id", "to": "target_node_id", 
        "relationship": "relationship_type",
        "description": "description of the relationship" }},
    ]
    }}
"""

PROMPTS[
    "gen_kg_prompt_v3"
] = """
-Goal-
Based on the provided snippet, construct a Knowledge Graph about {topic} which.

-Steps-
1. Identify all entities. For each identified entity, extract the following information:
- entity_name: Name of the entity, capitalized
- entity_type: Type of the entity (e.g., PERSON,ORGANIZATION,LOCATION,DATE,EVENT etc.)
- entity_description: Comprehensive description of the entity's attributes and activities

2. From the entities identified in step 1, identify all pairs of (source_entity, target_entity) that are *clearly related* to each other.
For each pair of related entities, extract the following information:
- source_entity: name of the source entity, as identified in step 1
- target_entity: name of the target entity, as identified in step 1
- relationship_description: explanation as to why you think the source entity and the target entity are related to each other
- relationship_strength: a numeric score indicating strength of the relationship between the source entity and target entity

3. Return output in a structured JSON format with two main sections: "nodes" for entities and "edges" for relationships.
   - Each node should have an "id" (numeric, starting from 0), "label" (entity name), "type" (entity type), and "description" (entity description)
   - Each edge should have "from" (source node id), "to" (target node id), "relationship" (general relationship type), "description" (relationship description), and "strength" (relationship strength)


######################
-Examples-
######################
Example 1:
Text:
The Verdantis's Central Institution is scheduled to meet on Monday and Thursday, with the institution planning to release its latest policy decision on Thursday at 1:30 p.m. PDT, followed by a press conference where Central Institution Chair Martin Smith will take questions. Investors expect the Market Strategy Committee to hold its benchmark interest rate steady in a range of 3.5%-3.75%.
######################
Output:
{{
  "nodes": [
    {{"id": "0", "label": "CENTRAL INSTITUTION", "type": "ORGANIZATION", "description": "The Central Institution is the Federal Reserve of Verdantis, which is setting interest rates on Monday and Thursday"}},
    {{"id": "1", "label": "MARTIN SMITH", "type": "PERSON", "description": "Martin Smith is the chair of the Central Institution"}},
    {{"id": "2", "label": "MARKET STRATEGY COMMITTEE", "type": "ORGANIZATION", "description": "The Central Institution committee makes key decisions about interest rates and the growth of Verdantis's money supply"}}
  ],
  "edges": [
    {{"from": "1", "to": "0", "relationship": "LEADERSHIP", "description": "Martin Smith is the Chair of the Central Institution and will answer questions at a press conference", "strength": 9}}
  ]
}}

######################
Example 2:
Text:
TechGlobal's (TG) stock skyrocketed in its opening day on the Global Exchange Thursday. But IPO experts warn that the semiconductor corporation's debut on the public markets isn't indicative of how other newly listed companies may perform.

TechGlobal, a formerly public company, was taken private by Vision Holdings in 2014. The well-established chip designer says it powers 85% of premium smartphones.
######################
Output:
{{
  "nodes": [
    {{"id": "0", "label": "TECHGLOBAL", "type": "ORGANIZATION", "description": "TechGlobal is a stock now listed on the Global Exchange which powers 85% of premium smartphones"}},
    {{"id": "1", "label": "VISION HOLDINGS", "type": "ORGANIZATION", "description": "Vision Holdings is a firm that previously owned TechGlobal"}}
  ],
  "edges": [
    {{"from": "0", "to": "1", "relationship": "OWNERSHIP", "description": "Vision Holdings formerly owned TechGlobal from 2014 until present", "strength": 5}}
  ]
}}

######################
Example 3:
Text:
Five Aurelians jailed for 8 years in Firuzabad and widely regarded as hostages are on their way home to Aurelia.

The swap orchestrated by Quintara was finalized when $8bn of Firuzi funds were transferred to financial institutions in Krohaara, the capital of Quintara.

The exchange initiated in Firuzabad's capital, Tiruzia, led to the four men and one woman, who are also Firuzi nationals, boarding a chartered flight to Krohaara.

They were welcomed by senior Aurelian officials and are now on their way to Aurelia's capital, Cashion.

The Aurelians include 39-year-old businessman Samuel Namara, who has been held in Tiruzia's Alhamia Prison, as well as journalist Durke Bataglani, 59, and environmentalist Meggie Tazbah, 53, who also holds Bratinas nationality.
######################
Output:
{{
  "nodes": [
    {{"id": "0", "label": "FIRUZABAD", "type": "GEO", "description": "Firuzabad held Aurelians as hostages"}},
    {{"id": "1", "label": "AURELIA", "type": "GEO", "description": "Country seeking to release hostages"}},
    {{"id": "2", "label": "QUINTARA", "type": "GEO", "description": "Country that negotiated a swap of money in exchange for hostages"}},
    {{"id": "3", "label": "TIRUZIA", "type": "GEO", "description": "Capital of Firuzabad where the Aurelians were being held"}},
    {{"id": "4", "label": "KROHAARA", "type": "GEO", "description": "Capital city in Quintara"}},
    {{"id": "5", "label": "CASHION", "type": "GEO", "description": "Capital city in Aurelia"}},
    {{"id": "6", "label": "SAMUEL NAMARA", "type": "PERSON", "description": "Aurelian who spent time in Tiruzia's Alhamia Prison"}},
    {{"id": "7", "label": "ALHAMIA PRISON", "type": "GEO", "description": "Prison in Tiruzia"}},
    {{"id": "8", "label": "DURKE BATAGLANI", "type": "PERSON", "description": "Aurelian journalist who was held hostage"}},
    {{"id": "9", "label": "MEGGIE TAZBAH", "type": "PERSON", "description": "Bratinas national and environmentalist who was held hostage"}}
  ],
  "edges": [
    {{"from": "0", "to": "1", "relationship": "DIPLOMATIC", "description": "Firuzabad negotiated a hostage exchange with Aurelia", "strength": 2}},
    {{"from": "2", "to": "1", "relationship": "DIPLOMATIC", "description": "Quintara brokered the hostage exchange between Firuzabad and Aurelia", "strength": 2}},
    {{"from": "2", "to": "0", "relationship": "DIPLOMATIC", "description": "Quintara brokered the hostage exchange between Firuzabad and Aurelia", "strength": 2}},
    {{"from": "6", "to": "7", "relationship": "IMPRISONMENT", "description": "Samuel Namara was a prisoner at Alhamia prison", "strength": 8}},
    {{"from": "6", "to": "9", "relationship": "ASSOCIATION", "description": "Samuel Namara and Meggie Tazbah were exchanged in the same hostage release", "strength": 2}},
    {{"from": "6", "to": "8", "relationship": "ASSOCIATION", "description": "Samuel Namara and Durke Bataglani were exchanged in the same hostage release", "strength": 2}},
    {{"from": "9", "to": "8", "relationship": "ASSOCIATION", "description": "Meggie Tazbah and Durke Bataglani were exchanged in the same hostage release", "strength": 2}},
    {{"from": "6", "to": "0", "relationship": "IMPRISONMENT", "description": "Samuel Namara was a hostage in Firuzabad", "strength": 2}},
    {{"from": "9", "to": "0", "relationship": "IMPRISONMENT", "description": "Meggie Tazbah was a hostage in Firuzabad", "strength": 2}},
    {{"from": "8", "to": "0", "relationship": "IMPRISONMENT", "description": "Durke Bataglani was a hostage in Firuzabad", "strength": 2}}
  ]
}}

######################
Output:
"""

# BACKBONE
PROMPTS[
    "gen_kg_prompt_v4"
] = """
You are a top-tier algorithm designed for extracting information in structured formats to build a knowledge graph about {topic}.


# Instructions
Adhere to the following steps:


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
- To construct the entity related pairs use the description that we found in step 1.


// Key Words
3. Identify high-level key words that summarize the main concepts, themes, or topics of the entire text. These should capture the overarching ideas present in the document.

// Consideration:
- Do not invent entities or relations not directly stated.

# Output: 
- Do not return any additional information other than the JSON format below:
{{
  "nodes": [
    {{"id": "node_id", "label": "entity_name", "description": "entity_description"}},
    {{"id": "0", "label": "Project Apollo", "description": "entity_description"}},
    {{"id": "1", "label": "NASA", "description": "entity_description"}},
    ...
  ],
  "edges": [
    {{"from": "source_node_id", "to": "target_node_id", "relationship": "relationship_type"}},
    {{"from": "0", "to": "1", "relationship": "lead_by"}},
    ...
  ]
  "keywords:"[
  {{"content_keywords": ["keyword1", "keyword2", ... ]
  ]
}}

"""


# FROM GPT not working quite well
PROMPTS[
    "gen_kg_prompt_v5"
] = """
You are a top-tier algorithm designed for extracting information in structured formats to build a knowledge graph about {topic}. From the provided text, emit **valid JSON only**, following this exact schema:

{{
  "nodes": [
    {{"id": "0", "label": "Full Entity Name (ACR)", "description": "≤40-word snippet-based description"}},
    …
  ],
  "edges": [
    {{"from": "0", "to": "1", "relationship": "lowercase_snake_case_relation"}},
    …
  ],
  "keywords": ["keyword1", "keyword2", …]   // 5-10 lower-case terms
}}

Rules
1. **Entities**
   • Use only facts explicitly present in the snippet.  
   • One node per unique real-world entity.  
   • `id` = sequential string (“0”, “1”…).  
   • If an entity is already an acronym, omit parentheses.

2. **Relationships**
   • Create an edge only when the snippet states or clearly implies the link.  
   • `relationship` ≤ 3 words, lower-case with underscores.  
   • No duplicate edges.

3. **Keywords**
   • Capture the snippet's main themes; no more than 10.  
   • Lower-case, single words.

Output **nothing** except the JSON. Ensure it parses without errors (no comments, no trailing commas, escape internal quotes).

"""


# INCLUDES: description of edges
PROMPTS[
    "gen_kg_prompt_v6"
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
  "questions": [
    "question1",
    "question2",
    ...
  ],
  
  "nodes": [
    {{
      "id": "node_id",
      "label": "entity_name",
      "description": "entity_description"
    }},
    {{
      "id": "0",
      "label": "Project Apollo",
      "description": "entity_description"
    }},
    {{
      "id": "1",
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
      "from": "0", 
      "to": "1", 
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
  ]
}}


"""

# INCLUDES: description of edges
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

# INCLUDES: questions about the snippet
PROMPTS[
    "gen_kg_prompt_v8"
] = """
You are a top-tier algorithm designed for extracting information in structured formats to build a knowledge graph about {topic}.


# Instructions
Adhere to the following steps:

// Question Exploration
0. Based on the snippet provided formulate a set of in-depth questions that cover all the aspects discussed in the snippet and that can only be answered with the information from the snippet. 


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
  "questions": [
    "question1",
    "question2",
    ...
  ],
  
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
  ]
}}


"""


##################################################
#            BUILD HIERARCHY KNOWLEDGE GRAPH
##################################################


PROMPTS[
    "build_hierarchy_kg_prompt_v1"
] = """

You are a top-tier algorithm designed for extracting
information in structured formats to build a knowledge graph.

Instructions:
1. Based on the provided Knoledge Graph, your task is to create unifying nodes that unify children nodes that share a similar relationship_type.
2. For each unifying node, 


create an unifying node that unifies these children nodes from the root node. Come up with the following information:
- Name: Give a short name for the unifying node that do not include the root's name and its children's name
- Description: Give a a short description (between 5 to 10 words) of the relation from the root to this unifying node.

Output:
- Do not return any additional information other than the JSON format below:
{{
  "unifying_node_name": "name",
  "description": "description",
}}

"""

PROMPTS[
    "build_hierarchy_kg_prompt_v2"
] = """

You are a top-tier algorithm designed for extracting
information in structured formats to build a knowledge graph.

Instructions:
1. Based on the provided Knowledge Graph, your task is to create unifying nodes that unify children nodes that share a similar relationship_type. Come up with the following information:


- Name: Give a short name for the unifying node that do not include the root's name and its children's name
- Description: Give a a short description (between 5 to 10 words) of the relation from the root to this unifying node.

Output:
- Do not return any additional information other than the JSON format below:
{{
  "unifying_node_name": "name",
  "description": "description",
}}

"""


PROMPTS[
    "build_hierarchy_kg_prompt_v3"
] = """
You are a top-tier algorithm designed for extracting information in structured formats to build a knowledge graph.

Goal: 
Improve the knowledge graph by categorizing nodes relating to each other such that you increase hierarchy of the graph where applicable. 

Instructions:
1. Based on the provided knowledge graph, identify all the edges that have the same relationship in meaning. Use the relationship description to help you understand the meaning. 
2. For edges with the same relationship in meaning, group the triples into chunks.
3. For each chunk, consider the target nodes. If a group of target nodes can be fitted into a unified category, place a third node with a meaningful label in between the initial source and target node.
4. Write a meaningful short description for the relationship between the original source node and the new node. Give this edge a label. 
5.  If applicable, rename the labels of edges connecting the new node and the target nodes such that they describe this relationship. Keep the relationship description that same. 

Output:
We should receive a knowledge graph in the same format as the input with better classification of the nodes by dividing nodes that connect to one common node into separate categories, if applicable. 

"""


PROMPTS[
    "build_hierarchy_kg_prompt_v4"
] = """
You are a top-tier algorithm designed for extracting information in structured formats to build a knowledge graph.

Instructions:
1. For each group of the 'kg_group' input check whether the 'children_nodes' can be linked with the 'parent_node' with an 'unifying_node' 
2. Analyze per group if all the children are suitable to be connected to this 'unifying_node'.
3. The criteria to decide whether a 'children_node' is suitable to be grouped is by taking a look at its `relationship_description`. If so then do the following:
3.1 Create a 'unifying_node' and give it a meaningful 'label', 'id', and 'description' 
3.2 For the edges from 'parent' to 'unifying_node' write a meaningful short description for the relationship between these two nodes.
3.3 For the edges from 'unifying_node' to 'children_nodes', keep the originally description from 'parent' to 'children_nodes' 
4. For the remaining nodes that are not in the 'kg_group' do not do anything. Conserve them in the graph as they are.

Output:
Provide a knowledge graph in the same format as the input 'kg'. Return in JSON format and nothing else.

"""


PROMPTS[
    "build_hierarchy_kg_prompt_v5"
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
      1. parent_node → unifying_node, with a short, meaningful relationship 
      2. unifying_node → child_node, retaining the original relationship_description.  
2. Leave all other nodes and edges unchanged.

Output:
Adhere to the JSON scheme of the provided input 'kg' with with new node(s) and adjusted edges.

"""

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

PROMPTS[
    "build_hierarchy_kg_prompt_v6"
] = """
You are a top-tier algorithm designed for extracting information in structured formats to build a knowledge graph.

Instructions:
1. For each group of the 'kg_group' input check whether the 'children_nodes' can be linked with the 'parent_node' with an 'unifying_node' 
2. Analyze per group if all the children are suitable to be connected to this 'unifying_node'.
3. The criteria to decide whether a 'children_node' is suitable to be grouped is by taking a look at its `relationship_description`. If so then do the following:
3.1 Create a 'unifying_node' and give it a meaningful 'label', 'id', and 'description' 
3.2 For the edges from 'parent' to 'unifying_node' write a meaningful short description for the relationship between these two nodes.
3.3 For the edges from 'unifying_node' to 'children_nodes', keep the originally description from 'parent' to 'children_nodes' 
4. For the remaining nodes that are not in the 'kg_group' do not do anything. Conserve them in the graph as they are.


Examples:
---  
Example 1

kg_group:  
{  
  "group1": {  
    "parent_node": "programming_paradigms",  
    "relation": "includes",  
    "children_nodes": [  
      {  
        "node_id": "object_oriented",  
        "relationship_description": "Object‑oriented programming organizes code around objects."  
      },  
      {  
        "node_id": "functional",  
        "relationship_description": "Functional programming treats computation as evaluation of pure functions."  
      }  
    ]  
  }  
}

kg:  
{  
  "nodes": [  
    { "id": "programming_paradigms", "label": "Programming Paradigms", "description": "Different overarching styles of programming." },  
    { "id": "object_oriented",      "label": "Object‑Oriented",        "description": "A paradigm based on objects and classes." },  
    { "id": "functional",           "label": "Functional",             "description": "A paradigm based on pure functions." },  
    { "id": "procedural",           "label": "Procedural",             "description": "A paradigm based on procedure calls." }  
  ],  
  "edges": [  
    {  
      "from": "programming_paradigms",  
      "to": "object_oriented",  
      "relationship": "includes",  
      "relationship_description": "Object‑oriented programming organizes code around objects."  
    },  
    {  
      "from": "programming_paradigms",  
      "to": "functional",  
      "relationship": "includes",  
      "relationship_description": "Functional programming treats computation as evaluation of pure functions."  
    },  
    {  
      "from": "programming_paradigms",  
      "to": "procedural",  
      "relationship": "includes",  
      "relationship_description": "Procedural programming consists of step‑by‑step instructions."  
    }  
  ]  
}

Output:  
kg:  
{  
  "nodes": [  
    { "id": "programming_paradigms", "label": "Programming Paradigms", "description": "Different overarching styles of programming." },  
    { "id": "object_oriented",      "label": "Object‑Oriented",        "description": "A paradigm based on objects and classes." },  
    { "id": "functional",           "label": "Functional",             "description": "A paradigm based on pure functions." },  
    { "id": "procedural",           "label": "Procedural",             "description": "A paradigm based on procedure calls." },  
    { "id": "oo_fp_paradigms",      "label": "OO & Functional Paradigms", "description": "Programming paradigms based on objects and pure functions." }  
  ],  
  "edges": [  
    {  
      "from": "programming_paradigms",  
      "to": "oo_fp_paradigms",  
      "relationship": "includes",  
      "relationship_description": "Includes object‑oriented and functional paradigms."  
    },  
    {  
      "from": "oo_fp_paradigms",  
      "to": "object_oriented",  
      "relationship": "includes",  
      "relationship_description": "Object‑oriented programming organizes code around objects."  
    },  
    {  
      "from": "oo_fp_paradigms",  
      "to": "functional",  
      "relationship": "includes",  
      "relationship_description": "Functional programming treats computation as evaluation of pure functions."  
    },  
    {  
      "from": "programming_paradigms",  
      "to": "procedural",  
      "relationship": "includes",  
      "relationship_description": "Procedural programming consists of step‑by‑step instructions."  
    }  
  ]  
}

---  
Example 2

kg_group:  
{  
  "group1": {  
    "parent_node": "fruits",  
    "relation": "is_a",  
    "children_nodes": [  
      {  
        "node_id": "orange",  
        "relationship_description": "Orange is a citrus fruit known for its sweet taste."  
      },  
      {  
        "node_id": "lemon",  
        "relationship_description": "Lemon is a citrus fruit known for its sour flavor."  
      }  
    ]  
  }  
}

kg:  
{  
  "nodes": [  
    { "id": "fruits",  "label": "Fruits", "description": "Edible plant seeds or seed‑pods, often sweet." },  
    { "id": "orange",  "label": "Orange", "description": "A round, orange‑skinned citrus fruit." },  
    { "id": "lemon",   "label": "Lemon",  "description": "A yellow, sour citrus fruit." },  
    { "id": "apple",   "label": "Apple",  "description": "A sweet pomaceous fruit." }  
  ],  
  "edges": [  
    {  
      "from": "fruits",  
      "to": "orange",  
      "relationship": "is_a",  
      "relationship_description": "Orange is a citrus fruit known for its sweet taste."  
    },  
    {  
      "from": "fruits",  
      "to": "lemon",  
      "relationship": "is_a",  
      "relationship_description": "Lemon is a citrus fruit known for its sour flavor."  
    },  
    {  
      "from": "fruits",  
      "to": "apple",  
      "relationship": "is_a",  
      "relationship_description": "Apple is a common sweet fruit."  
    }  
  ]  
}

Output:  
kg:  
{  
  "nodes": [  
    { "id": "fruits",     "label": "Fruits", "description": "Edible plant seeds or seed‑pods, often sweet." },  
    { "id": "orange",     "label": "Orange", "description": "A round, orange‑skinned citrus fruit." },  
    { "id": "lemon",      "label": "Lemon",  "description": "A yellow, sour citrus fruit." },  
    { "id": "apple",      "label": "Apple",  "description": "A sweet pomaceous fruit." },  
    { "id": "citrus_fruits", "label": "Citrus Fruits", "description": "Fruits known for their juicy segments and sweet or sour flavor." }  
  ],  
  "edges": [  
    {  
      "from": "fruits",  
      "to": "citrus_fruits",  
      "relationship": "includes",  
      "relationship_description": "Includes orange and lemon as citrus fruits."  
    },  
    {  
      "from": "citrus_fruits",  
      "to": "orange",  
      "relationship": "is_a",  
      "relationship_description": "Orange is a citrus fruit known for its sweet taste."  
    },  
    {  
      "from": "citrus_fruits",  
      "to": "lemon",  
      "relationship": "is_a",  
      "relationship_description": "Lemon is a citrus fruit known for its sour flavor."  
    },  
    {  
      "from": "fruits",  
      "to": "apple",  
      "relationship": "is_a",  
      "relationship_description": "Apple is a common sweet fruit."  
    }  
  ]  
}

---  
Example 3

kg_group:  
{  
  "group1": {  
    "parent_node": "shapes",  
    "relation": "type_of",  
    "children_nodes": [  
      {  
        "node_id": "square",  
        "relationship_description": "Square is a quadrilateral with four equal sides."  
      },  
      {  
        "node_id": "rectangle",  
        "relationship_description": "Rectangle is a quadrilateral with opposite sides equal."  
      }  
    ]  
  }  
}

kg:  
{  
  "nodes": [  
    { "id": "shapes",    "label": "Shapes",    "description": "Basic geometric figures." },  
    { "id": "circle",    "label": "Circle",    "description": "All points equidistant from a center." },  
    { "id": "square",    "label": "Square",    "description": "A quadrilateral with four equal sides." },  
    { "id": "rectangle", "label": "Rectangle", "description": "A quadrilateral with four right angles." }  
  ],  
  "edges": [  
    {  
      "from": "shapes",  
      "to": "circle",  
      "relationship": "type_of",  
      "relationship_description": "Circle is a basic geometric shape."  
    },  
    {  
      "from": "shapes",  
      "to": "square",  
      "relationship": "type_of",  
      "relationship_description": "Square is a quadrilateral with four equal sides."  
    },  
    {  
      "from": "shapes",  
      "to": "rectangle",  
      "relationship": "type_of",  
      "relationship_description": "Rectangle is a quadrilateral with opposite sides equal."  
    }  
  ]  
}

Output:  
kg:  
{  
  "nodes": [  
    { "id": "shapes",        "label": "Shapes",    "description": "Basic geometric figures." },  
    { "id": "circle",        "label": "Circle",    "description": "All points equidistant from a center." },  
    { "id": "square",        "label": "Square",    "description": "A quadrilateral with four equal sides." },  
    { "id": "rectangle",     "label": "Rectangle", "description": "A quadrilateral with four right angles." },  
    { "id": "quadrilaterals","label": "Quadrilaterals","description": "Four-sided polygons with various side properties." }  
  ],  
  "edges": [  
    {  
      "from": "shapes",  
      "to": "quadrilaterals",  
      "relationship": "includes",  
      "relationship_description": "Includes square and rectangle as quadrilaterals."  
    },  
    {  
      "from": "quadrilaterals",  
      "to": "square",  
      "relationship": "type_of",  
      "relationship_description": "Square is a quadrilateral with four equal sides."  
    },  
    {  
      "from": "quadrilaterals",  
      "to": "rectangle",  
      "relationship": "type_of",  
      "relationship_description": "Rectangle is a quadrilateral with opposite sides equal."  
    },  
    {  
      "from": "shapes",  
      "to": "circle",  
      "relationship": "type_of",  
      "relationship_description": "Circle is a basic geometric shape."  
    }  
  ]  
}


Output:
Adhere to the JSON scheme of the provided input 'kg' with with new node(s) and adjusted edges.

"""


PROMPTS[
    "build_hierarchy_kg_prompt_v7"
] = """
You are an expert KG-builder.

**Inputs**  
1. “kg”: a JSON with  
   - nodes: [ {id, label, description}, … ]  
   - edges: [ {from, to, relationship, relationship_description}, … ]  
2. “kg_group”: a list of group instructions:  
   - parent_node: the ID of a node in kg  
   - relation: the edge label that all children share  
   - children_nodes: [  
       { node_id: <childID>, relationship_description: <text> }, …  
     ]

**For each group** in `kg_group`, do this:  
1. **Validate**  
   - Keep only those children where an edge exists in `kg["edges"]` with  
     `from == parent_node`, `to == childID`, `relationship == relation`,  
     and exactly matching `relationship_description`.  

2. **Create one “unifying node”**  
   - `id`: `"unifier_<relation>_<uniqueSuffix>"` (you choose a short unique suffix)  
   - `label`: `"a concise human-readable name"`  
   - **`description`**: write **one sentence** summarizing *what those N children have in common*  

3. **Rewire edges**  
   a. **Remove** the original edges `(parent_node → childID)` for the validated children.  
   b. **Add** exactly two kinds of new edges:  
      1. **Parent → Unifier**  
         {{
           "from": parent_node,
           "to": unifier_id,
           "relationship": <a new rational relationship>,
           "relationship_description": <a short, meaningful relationship>
         }}
      2. **Unifier → Child** (for each child)  
         {{
           "from": unifier_id,
           "to": childID,
           "relationship": relation,
           "relationship_description": <same text as the original child.relationship_description>
         }}

4. **Leave all other nodes and edges unchanged.**

Output:
Adhere to the JSON scheme of the provided input 'kg'.

"""


EXAMPLES[
    "gen_hierarchy_v0"
] = """

---  
Example 1

kg_group:
{
  "group1": {
    "parent_node": "programming_languages",
    "relation": "paradigm",
    "children_nodes": [
      { "node_id": "java",   "relationship_description": "Java is an object‑oriented language." },
      { "node_id": "python", "relationship_description": "Python supports object‑oriented programming." }
    ]
  }
}

kg:
{
  "nodes": [
    { "id": "programming_languages", "label": "Programming Languages", "description": "Languages for writing software." },
    { "id": "java",                  "label": "Java",                  "description": "An object‑oriented language." },
    { "id": "python",                "label": "Python",                "description": "Supports multiple paradigms." },
    { "id": "sql",                   "label": "SQL",                   "description": "A database query language." }
  ],
  "edges": [
    { "from": "programming_languages", "to": "java",   "relationship": "paradigm", "relationship_description": "Java is an object‑oriented language." },
    { "from": "programming_languages", "to": "python", "relationship": "paradigm", "relationship_description": "Python supports object‑oriented programming." },
    { "from": "programming_languages", "to": "sql",    "relationship": "category", "relationship_description": "SQL is a database query language." }
  ]
}

Output:
kg:  
{
  "nodes": [
    { "id": "programming_languages",                 "label": "Programming Languages",     "description": "Languages for writing software." },
    { "id": "programming_languages_oop",              "label": "OOP Languages",           "description": "Languages following the object‑oriented paradigm." },
    { "id": "java",                                   "label": "Java",                    "description": "An object‑oriented language." },
    { "id": "python",                                 "label": "Python",                  "description": "Supports multiple paradigms." },
    { "id": "sql",                                    "label": "SQL",                     "description": "A database query language." }
  ],
  "edges": [
    {
      "from": "programming_languages",
      "to": "programming_languages_oop",
      "relationship": "organizes_by_paradigm",
      "relationship_description": "Segments programming languages into object‑oriented ones."
    },
    {
      "from": "programming_languages_oop",
      "to": "java",
      "relationship": "paradigm",
      "relationship_description": "Java is an object‑oriented language."
    },
    {
      "from": "programming_languages_oop",
      "to": "python",
      "relationship": "paradigm",
      "relationship_description": "Python supports object‑oriented programming."
    },
    {
      "from": "programming_languages",
      "to": "sql",
      "relationship": "category",
      "relationship_description": "SQL is a database query language."
    }
  ]
}


---

Example 2:

kg_group:
{
  "group1": {
    "parent_node": "vehicles",
    "relation": "fuel_type",
    "children_nodes": [
      { "node_id": "tesla_model_s", "relationship_description": "Tesla Model S runs on electric power." },
      { "node_id": "nissan_leaf",    "relationship_description": "Nissan Leaf is an electric car." }
    ]
  }
}

kg:
{
  "nodes": [
    { "id": "vehicles",       "label": "Vehicles",       "description": "Means of transport." },
    { "id": "tesla_model_s",  "label": "Tesla Model S",  "description": "An electric sedan." },
    { "id": "nissan_leaf",    "label": "Nissan Leaf",    "description": "A compact electric car." },
    { "id": "ford_f150",      "label": "Ford F‑150",     "description": "A petrol‑powered pickup truck." }
  ],
  "edges": [
    { "from": "vehicles", "to": "tesla_model_s", "relationship": "fuel_type", "relationship_description": "Tesla Model S runs on electric power." },
    { "from": "vehicles", "to": "nissan_leaf",   "relationship": "fuel_type", "relationship_description": "Nissan Leaf is an electric car." },
    { "from": "vehicles", "to": "ford_f150",     "relationship": "fuel_type", "relationship_description": "Ford F‑150 uses petrol." }
  ]
}


Output
kg:
{
  "nodes": [
    { "id": "vehicles",                   "label": "Vehicles",             "description": "Means of transport." },
    { "id": "vehicles_electric",          "label": "Electric Vehicles",    "description": "Vehicles powered by electricity." },
    { "id": "tesla_model_s",              "label": "Tesla Model S",        "description": "An electric sedan." },
    { "id": "nissan_leaf",                "label": "Nissan Leaf",          "description": "A compact electric car." },
    { "id": "ford_f150",                  "label": "Ford F‑150",           "description": "A petrol‑powered pickup truck." }
  ],
  "edges": [
    {
      "from": "vehicles",
      "to": "vehicles_electric",
      "relationship": "groups_electric",
      "relationship_description": "Collects all electric‑powered vehicles."
    },
    {
      "from": "vehicles_electric",
      "to": "tesla_model_s",
      "relationship": "fuel_type",
      "relationship_description": "Tesla Model S runs on electric power."
    },
    {
      "from": "vehicles_electric",
      "to": "nissan_leaf",
      "relationship": "fuel_type",
      "relationship_description": "Nissan Leaf is an electric car."
    },
    {
      "from": "vehicles",
      "to": "ford_f150",
      "relationship": "fuel_type",
      "relationship_description": "Ford F‑150 uses petrol."
    }
  ]
}

---

Example 3

kg_group:
{
  "group1": {
    "parent_node": "fruits",
    "relation": "color",
    "children_nodes": [
      { "node_id": "apple",       "relationship_description": "Apples are red when ripe." },
      { "node_id": "strawberry",  "relationship_description": "Strawberries have a red exterior." }
    ]
  }
}


kg:
{
  "nodes": [
    { "id": "fruits",       "label": "Fruits",       "description": "Edible plant products." },
    { "id": "apple",        "label": "Apple",        "description": "A sweet, crispy fruit." },
    { "id": "strawberry",   "label": "Strawberry",   "description": "A small red fruit." },
    { "id": "banana",       "label": "Banana",       "description": "A yellow tropical fruit." }
  ],
  "edges": [
    { "from": "fruits", "to": "apple",      "relationship": "color", "relationship_description": "Apples are red when ripe." },
    { "from": "fruits", "to": "strawberry", "relationship": "color", "relationship_description": "Strawberries have a red exterior." },
    { "from": "fruits", "to": "banana",     "relationship": "color", "relationship_description": "Bananas are yellow when ripe." }
  ]
}


Output
kg:
{
  "nodes": [
    { "id": "fruits",               "label": "Fruits",             "description": "Edible plant products." },
    { "id": "fruits_red",           "label": "Red Fruits",        "description": "Fruits characterized by red color." },
    { "id": "apple",                "label": "Apple",             "description": "A sweet, crispy fruit." },
    { "id": "strawberry",           "label": "Strawberry",        "description": "A small red fruit." },
    { "id": "banana",               "label": "Banana",            "description": "A yellow tropical fruit." }
  ],
  "edges": [
    {
      "from": "fruits",
      "to": "fruits_red",
      "relationship": "categorizes_by_color",
      "relationship_description": "Groups fruits that share the red color trait."
    },
    {
      "from": "fruits_red",
      "to": "apple",
      "relationship": "color",
      "relationship_description": "Apples are red when ripe."
    },
    {
      "from": "fruits_red",
      "to": "strawberry",
      "relationship": "color",
      "relationship_description": "Strawberries have a red exterior."
    },
    {
      "from": "fruits",
      "to": "banana",
      "relationship": "color",
      "relationship_description": "Bananas are yellow when ripe."
    }
  ]
}
"""


EXAMPLES[
    "gen_hierarchy_v1"
] = """
---  
Example 1

kg_group:  
{  
  "group1": {  
    "parent_node": "programming_paradigms",  
    "relation": "includes",  
    "children_nodes": [  
      {  
        "node_id": "object_oriented",  
        "relationship_description": "Object‑oriented programming organizes code around objects."  
      },  
      {  
        "node_id": "functional",  
        "relationship_description": "Functional programming treats computation as evaluation of pure functions."  
      }  
    ]  
  }  
}

kg:  
{  
  "nodes": [  
    { "id": "programming_paradigms", "label": "Programming Paradigms", "description": "Different overarching styles of programming." },  
    { "id": "object_oriented",      "label": "Object‑Oriented",        "description": "A paradigm based on objects and classes." },  
    { "id": "functional",           "label": "Functional",             "description": "A paradigm based on pure functions." },  
    { "id": "procedural",           "label": "Procedural",             "description": "A paradigm based on procedure calls." }  
  ],  
  "edges": [  
    {  
      "from": "programming_paradigms",  
      "to": "object_oriented",  
      "relationship": "includes",  
      "relationship_description": "Object‑oriented programming organizes code around objects."  
    },  
    {  
      "from": "programming_paradigms",  
      "to": "functional",  
      "relationship": "includes",  
      "relationship_description": "Functional programming treats computation as evaluation of pure functions."  
    },  
    {  
      "from": "programming_paradigms",  
      "to": "procedural",  
      "relationship": "includes",  
      "relationship_description": "Procedural programming consists of step‑by‑step instructions."  
    }  
  ]  
}

Output:  
kg:  
{  
  "nodes": [  
    { "id": "programming_paradigms", "label": "Programming Paradigms", "description": "Different overarching styles of programming." },  
    { "id": "object_oriented",      "label": "Object‑Oriented",        "description": "A paradigm based on objects and classes." },  
    { "id": "functional",           "label": "Functional",             "description": "A paradigm based on pure functions." },  
    { "id": "procedural",           "label": "Procedural",             "description": "A paradigm based on procedure calls." },  
    { "id": "oo_fp_paradigms",      "label": "OO & Functional Paradigms", "description": "Programming paradigms based on objects and pure functions." }  
  ],  
  "edges": [  
    {  
      "from": "programming_paradigms",  
      "to": "oo_fp_paradigms",  
      "relationship": "includes",  
      "relationship_description": "Includes object‑oriented and functional paradigms."  
    },  
    {  
      "from": "oo_fp_paradigms",  
      "to": "object_oriented",  
      "relationship": "includes",  
      "relationship_description": "Object‑oriented programming organizes code around objects."  
    },  
    {  
      "from": "oo_fp_paradigms",  
      "to": "functional",  
      "relationship": "includes",  
      "relationship_description": "Functional programming treats computation as evaluation of pure functions."  
    },  
    {  
      "from": "programming_paradigms",  
      "to": "procedural",  
      "relationship": "includes",  
      "relationship_description": "Procedural programming consists of step‑by‑step instructions."  
    }  
  ]  
}

---  
Example 2

kg_group:  
{  
  "group1": {  
    "parent_node": "fruits",  
    "relation": "is_a",  
    "children_nodes": [  
      {  
        "node_id": "orange",  
        "relationship_description": "Orange is a citrus fruit known for its sweet taste."  
      },  
      {  
        "node_id": "lemon",  
        "relationship_description": "Lemon is a citrus fruit known for its sour flavor."  
      }  
    ]  
  }  
}

kg:  
{  
  "nodes": [  
    { "id": "fruits",  "label": "Fruits", "description": "Edible plant seeds or seed‑pods, often sweet." },  
    { "id": "orange",  "label": "Orange", "description": "A round, orange‑skinned citrus fruit." },  
    { "id": "lemon",   "label": "Lemon",  "description": "A yellow, sour citrus fruit." },  
    { "id": "apple",   "label": "Apple",  "description": "A sweet pomaceous fruit." }  
  ],  
  "edges": [  
    {  
      "from": "fruits",  
      "to": "orange",  
      "relationship": "is_a",  
      "relationship_description": "Orange is a citrus fruit known for its sweet taste."  
    },  
    {  
      "from": "fruits",  
      "to": "lemon",  
      "relationship": "is_a",  
      "relationship_description": "Lemon is a citrus fruit known for its sour flavor."  
    },  
    {  
      "from": "fruits",  
      "to": "apple",  
      "relationship": "is_a",  
      "relationship_description": "Apple is a common sweet fruit."  
    }  
  ]  
}

Output:  
kg:  
{  
  "nodes": [  
    { "id": "fruits",     "label": "Fruits", "description": "Edible plant seeds or seed‑pods, often sweet." },  
    { "id": "orange",     "label": "Orange", "description": "A round, orange‑skinned citrus fruit." },  
    { "id": "lemon",      "label": "Lemon",  "description": "A yellow, sour citrus fruit." },  
    { "id": "apple",      "label": "Apple",  "description": "A sweet pomaceous fruit." },  
    { "id": "citrus_fruits", "label": "Citrus Fruits", "description": "Fruits known for their juicy segments and sweet or sour flavor." }  
  ],  
  "edges": [  
    {  
      "from": "fruits",  
      "to": "citrus_fruits",  
      "relationship": "includes",  
      "relationship_description": "Includes orange and lemon as citrus fruits."  
    },  
    {  
      "from": "citrus_fruits",  
      "to": "orange",  
      "relationship": "is_a",  
      "relationship_description": "Orange is a citrus fruit known for its sweet taste."  
    },  
    {  
      "from": "citrus_fruits",  
      "to": "lemon",  
      "relationship": "is_a",  
      "relationship_description": "Lemon is a citrus fruit known for its sour flavor."  
    },  
    {  
      "from": "fruits",  
      "to": "apple",  
      "relationship": "is_a",  
      "relationship_description": "Apple is a common sweet fruit."  
    }  
  ]  
}

---  
Example 3

kg_group:  
{  
  "group1": {  
    "parent_node": "shapes",  
    "relation": "type_of",  
    "children_nodes": [  
      {  
        "node_id": "square",  
        "relationship_description": "Square is a quadrilateral with four equal sides."  
      },  
      {  
        "node_id": "rectangle",  
        "relationship_description": "Rectangle is a quadrilateral with opposite sides equal."  
      }  
    ]  
  }  
}

kg:  
{  
  "nodes": [  
    { "id": "shapes",    "label": "Shapes",    "description": "Basic geometric figures." },  
    { "id": "circle",    "label": "Circle",    "description": "All points equidistant from a center." },  
    { "id": "square",    "label": "Square",    "description": "A quadrilateral with four equal sides." },  
    { "id": "rectangle", "label": "Rectangle", "description": "A quadrilateral with four right angles." }  
  ],  
  "edges": [  
    {  
      "from": "shapes",  
      "to": "circle",  
      "relationship": "type_of",  
      "relationship_description": "Circle is a basic geometric shape."  
    },  
    {  
      "from": "shapes",  
      "to": "square",  
      "relationship": "type_of",  
      "relationship_description": "Square is a quadrilateral with four equal sides."  
    },  
    {  
      "from": "shapes",  
      "to": "rectangle",  
      "relationship": "type_of",  
      "relationship_description": "Rectangle is a quadrilateral with opposite sides equal."  
    }  
  ]  
}

Output:  
kg:  
{  
  "nodes": [  
    { "id": "shapes",        "label": "Shapes",    "description": "Basic geometric figures." },  
    { "id": "circle",        "label": "Circle",    "description": "All points equidistant from a center." },  
    { "id": "square",        "label": "Square",    "description": "A quadrilateral with four equal sides." },  
    { "id": "rectangle",     "label": "Rectangle", "description": "A quadrilateral with four right angles." },  
    { "id": "quadrilaterals","label": "Quadrilaterals","description": "Four-sided polygons with various side properties." }  
  ],  
  "edges": [  
    {  
      "from": "shapes",  
      "to": "quadrilaterals",  
      "relationship": "includes",  
      "relationship_description": "Includes square and rectangle as quadrilaterals."  
    },  
    {  
      "from": "quadrilaterals",  
      "to": "square",  
      "relationship": "type_of",  
      "relationship_description": "Square is a quadrilateral with four equal sides."  
    },  
    {  
      "from": "quadrilaterals",  
      "to": "rectangle",  
      "relationship": "type_of",  
      "relationship_description": "Rectangle is a quadrilateral with opposite sides equal."  
    },  
    {  
      "from": "shapes",  
      "to": "circle",  
      "relationship": "type_of",  
      "relationship_description": "Circle is a basic geometric shape."  
    }  
  ]  
}

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
    "cluster_entities_prompt_v0"
] = """
You are a top-tier algorithm designed for clustering information in structured format to build a knowledge graph.

Instructions:
- Given this set of nodes, cluster those that have a similar label name, with different tenses, plural forms, stem forms, or cases. 

Output:
Return populated list only if you find items that clearly belong together, else return empty list.

"""

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
    "expand_kg_prompt_v0"
] = """
Given this graph, we would like to expand our knowledge graph to better understand the topic: {topic}. Expand in this context means to broaden our current understanding on the topic.

Knowledge Graph:
{kg}

Output:
- Provide questions that will allows to investigate {topic} further. Take into account was it was discussed by the Knowledge Graph and then provide a top-down questions of importance, where top is a query that would contribute to our outmost for better comprehend {topic}.
Adhere to the following format:
- Question1
- Question2
- ...

"""

PROMPTS[
    "expand_kg_prompt_v1"
] = """

Knowledge Graph:
{kg}

Based on this KG, which represents our current understanding of the topic: {topic} we would like to expand/investigate the topic further. 

Instructions: 
1. Give queries that could be used as a search keywords to further understand the topic.
Note: we have already explored the 'questions' included in the JSON file.

Considerations: 
- We want to have a balance of queries such that we analyse whether we need to expand a node
    - consider formulating general and in-depth queries based on the following definitions: 
        - General queries: are questions that could broaden our understanding of the topic 
        - In-depth queries: are queries that could deepen our understanding of the topic
- Analyse the state of the graph to see how much importance to give to general queries vs. in-depth queries. 

Output:
Adhere to the following format and do not output anything else:
- General query1:
- General query2:
- ...
- In-depth query1:
- In-depth query2:
- ...

"""

PROMPTS[
    "expand_kg_prompt_v2"
] = """

Given the provided knowledge graph in JSON format, we would like to expand our knowledge to better understand the topic: {topic}. Expand in this context means to broaden our current understanding on the topic.

Knowledge Graph:
{kg}

Give me queries about topic X based on the given knowledge graph that cover at least one of each of these themes: 

- big picture
- it's core concepts
- it's history and evolution
- it's applications and real-world use
- it's debates, challenges, and limitations
- it's cutting edge and future trends

Adhere to the following format:
- Question1
- Question2
- ...

"""

# BROAD CATEGORIES
PROMPTS[
    "expand_kg_prompt_v3"
] = """
{kg}

You are a postdoc researcher that is investigating about the topic: {topic}. You have done literature review about the topic and built a knowledge graph that captures the key concepts, relationships, and reliable sources that you have identified so far.

As a skilled researcher you are fully aware that your current understanding of the topic can be improved. You decide to analyze the KG in detail and identify the most important or under-explored nodes in the graph to continue expanding your understanding about {topic}.

Instructions:
1. Think like a researcher and formulate queries from different perspectives or categories that you deem important to continue expanding your understanding about the topic.
2. For each query, provide one sentence explaining why answering this question would be beneficial to expand your understanding about the topic.

Considerations:
- Avoid repeating concepts already well covered by the existing knowledge graph. 

Output:
Adhere to the following format and do not output anything else:

- Query 1: 
- Explanation 1:
- Query 2:
- Explanation 2:
- ...
- ...

"""


PROMPTS[
    "expand_kg_prompt_v5"
] = """
Knowledge graph:
{kg}

You are a helpful assistance working for a research team on expanding the provided knowledge graph. Your task is to come up with queries to deepen (depth) and expand (breath) your understanding of the topic: {topic}. 

Instructions:
1. Use your common sense and reason which which areas, categories or concepts are under-explored to fully understand: What is {topic}?

Considerations: 
- We want to have a balance of queries such that we analyse whether we need to expand a node
    - consider formulating general and in-depth queries based on the following definitions: 
        - General queries: are questions that could broaden our understanding of the topic 
        - In-depth queries: are queries that could deepen our understanding of the topic
- Analyse the state of the graph to see how much importance to give to general queries vs. in-depth queries. 
- For each query, provide one sentence explaining why answering this question would be beneficial to expand your understanding about the topic.

Output:
Adhere to the following format and do not output anything else:
- [General Query 1]:
- [Explanation 1]: 
- [General Query 2]:
- [Explanation 2]: 
- ...
- [In-depth Query 1]: 
- [Explanation 1]: 
- [In-depth Query 1]: 
- [Explanation 2]: 
- ...
"""

PROMPTS[
    "expand_kg_prompt_v6"
] = """
You are a helpful assistance working for a research team on expanding the provided knowledge graph. Your task is to come up with queries to deepen (depth) and expand (breath) your understanding of the topic: {topic}. 

Instructions:
1. Use your common sense and reason which which areas, categories or concepts are under-explored to fully understand: What is {topic}?

Considerations: 
- We want to have a balance of queries such that we analyse whether we need to expand a node
- Consider formulating general and in-depth queries based on the following definitions: 
        - General queries: are questions that could broaden our understanding of the topic 
        - In-depth queries: are queries that could deepen our understanding of the topic
- Analyse the state of the graph to see how much importance to give to general queries vs. in-depth queries. 
- For each query, provide one sentence explaining why answering this question would be beneficial to expand your understanding about the topic.
- Note: the provided KG in JSON format has provided you a set of questions that we have already explored. Do not repeat them but rather analyze them to aid you in your task.

Output:
Adhere to the following format and do not output anything else:
{{
  "general_queries": [
    {{
      "query1": "General Query 1",
      "explanation1": "Explanation 1"
    }},
    {{
      "query2": "General Query 2",
      "explanation2": "Explanation 2"
    }},
    …
  ],
  "in_depth_queries": [
    {{
      "query1": "In-depth Query 1",
      "explanation1": "Explanation 1"
    }},
    {{
      "query2": "In-depth Query 2",
      "explanation2": "Explanation 2"
    }},
    …
  ]
}}

"""

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
    "questions_to_queries_prompt_v0"
] = """
You are an expert researcher on the topic provided. Your task is to read each of the `general_queries` and `in_depth_queries` and based on the explanation provided, generate a set of queries that can be used to search for information on the topic. Select which ones are the most relevant and useful to expand our understanding of the topic. If one question you consider is not useful, you can ignore it.

Instructions:
- As this is a research task that would be read by {audience}, analyze which set of queries would expand our breath and depth of the topic treated.
- The max num queries you can generate is 10 so think well what can we use to expand our understanding of the topic.
- Your queries must be short and clear as we will use them to search information in Google search. Avoid W questions focus only on the keywords that are important to search for information.
- Return all queries from top to bottom, where the first query is the most important one to search for information and the last one is the least important one.

Output:
- Adhere to the following format and do not add any other text:
{{
    "combined_queries": [
        "query_1",
        "query_2",
        ...
        "query_n"
    ]
}}

"""

PROMPTS[
    "questions_to_queries_prompt_v1"
] = """"
You want to answer the questions for {audience} using Google search. What do you type in the search box?
Write the queries you will use in the following format:
{{
    "queries": [
        "query 1",
        "query 2",
        ...
        "query n"
    ]
}}
  """

PROMPTS[
    "questions_to_queries_prompt_v2"
] = """"
You are an expert researcher on the given topic. Your task is to review the lists `general_queries` and `in_depth_queries` and, based on the instructions, choose up to five precise search strings that will yield the most useful information.

Instructions:
- Think from the perspective of {audience}: select queries that broaden and deepen understanding of the topic.
- Produce exactly five queries.
- Keep each query concise and focused on key terms—no question words (e.g., who, what, why).
- Rank them: the first is highest priority; the fifth is lowest.
- Omit any query that won't add value.

Output:
- Stick to this new JSON structure, and do not add any extra text. Combine all queries into the key `combined_queries`, where the first query is the most important one to search for information and the last one is the least important one.
{{
    "combined_queries": [
        "query 1",
        "query 2",
        ...
        "query n"
    ]
}}
"""


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

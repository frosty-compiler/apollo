PROMPTS = {}

##################################################
#               OUTLINE CONSTRUCTION
##################################################

PROMPTS[
    "write_outline_kg_v0"
] = """
Based on this knowledge graph construct an outline for a Wikipedia Article that covers all the nodes and edges in the graph. The outline should be structured with headings and subheadings, and should build a comprehensive overview of the topic.
Here is the format of your writing:
1. Use "#" Title" to indicate section title, "##" Title" to indicate subsection title, "###" Title" to indicate subsubsection title, and so on.
2. Do not include other information.
3. Do not include topic name itself in the outline.
"""

PROMPTS[
    "write_outline_kg_v1"
] = """
Based on this knowledge graph construct an outline for a Wikipedia Article that covers all the nodes and edges in the graph. The outline should be structured with headings and subheadings, and should build a comprehensive overview of the topic.

Please keep the number of (h1) sections between 6 to 9. See what is relevant for a general audience that wants to know about this topic. See what it would be insighfull and give a clear overview of what the topic is about.

Remember, the KG is a representation of what we know about the topic but we need to write an outline that is comprehensive and understandable for a general audience.

Also in your outline, do not include an "Introduction" section, as we will instead generate a "Summary" section like in Wikipedia-pages so account for this when creating the outline.

Here is the format of your writing:
1. Use "#" Title" to indicate section title, "##" Title" to indicate subsection title, "###" Title" to indicate subsubsection title, and so on.
2. Do not include other information.
3. Do not include topic name itself in the outline.
"""


##################################################
#               OUTLINE REFINEMENT
##################################################

PROMPTS[
    "refine_outline_kg_v0"
] = """
You are an expert Wikipedia writer. Your task is to refine the following draft outline to meet Wikipedia standards for the topic: '{topic}'.

Please ensure the outline is clear, relevant, and informative for a general audience seeking to understand the topic. Remove any unrelated sections, improve structural coherence, and organize the content according to standard Wikipedia article conventions.

The final outline should include between 5 to 8 top-level (H1) sections. If the current outline already meets this requirement and is structurally sound, simply return it as is.

Output the revised outline in the same format, with no additional commentary.
"""


PROMPTS[
    "refine_outline_kg_v1"
] = """
You are an expert Wikipedia writer. Your task is to refine the following draft outline for the topic: "{topic}".

The outline was generated from a knowledge graph, which may contain noisy or overly specific information. Therefore, your task is to ensure that all sections are:

1. Directly relevant to the topic.
2. Useful for a general audience seeking to understand the subject.
3. Structured according to Wikipedia article conventions.

Please remove any sections that are not clearly related to the main topic, are too narrow or tangential, or are unlikely to be helpful to non-expert readers.

Your final outline must include between 5 and 8 top-level (H1) sections. Use "#" for H1, "##" for H2, "###" for H3, and so on. 

Return the cleaned-up outline in the same format, with no additional explanations.

"""


##################################################
#                 URL TO OUTLINE
##################################################

PROMPTS[
    "url_to_outline_v0"
] = """
You are an expert Wikipedia editor that is expert in {topic}. Your task is to map relevant nodes from the provided knowledge graph to each section of the outline provided.

Instructions:
1. For each section of the outline, provide all 'urls' of the nodes that are most relevant to explain that section.
2. Do consider all nodes from the knowledge graph and map its urls to the sections of the outline.
3. Ensure complete coverage - every relevant node should be mapped to at least one section.

Output:
- Adhere to the following format and do not include any other information:
{{
    "section_title": "# ",
    "urls": [
        "url1",
        "url2",
        "url3",
        ...
    ]
    "section_title": "Another Section title",
    "urls": [
        "url4",
        "url2",
        "url5",
        ...
    ]
}}


"""

PROMPTS[
    "url_to_outline_v1"
] = """
You are an expert Wikipedia editor that is expert in {topic}. Your task is to map relevant URLs of the nodes from the provided knowledge graph to each section of the outline provided.

Instructions:
1. For each section of the outline, provide all 'urls' of the nodes that are most relevant to explain that section.
2. Do consider all nodes from the knowledge graph and map its urls to the sections of the outline.

Output:
- Adhere to the input outline JSON format and fill the list.:


"""

PROMPTS[
    "url_to_outline_v2"
] = """

You are an expert Wikipedia editor specializing in {topic}. Your task is to map the URL nodes from the provided knowledge graph to the sections of the outline provided.

Instructions:
1. For each section in the outline, fill the empty array with URLs of the most relevant nodes from the knowledge graph.
2. To determine the relevance of a node, loop over the nodes per section, see whether the label of that node is relevant to the section title, and if it is not enough, also check the description of the node. 
3. If the node is relevant, add its URL to the list of URLs for that section.

Constraint:
- Copy EXACTLY how the URL of the relevant node to the outline section list. Do not make any changes to the URL.
- A section can have multiple URLs

Output:
- Adhere to the input outline JSON format and do not include any other information.
"""

PROMPTS[
    "url_to_outline_v3"
] = """
You are an expert Wikipedia editor on {{topic}}. You’ll be given:

1. An outline in JSON format, where each section heading is a key with an empty array as its value.
2. A knowledge-graph JSON object with nodes that have `label`, `description`, and `url`.

Your task is to populate each section’s array with the URLs of the most relevant nodes, based on these rules:

• Relevance: A node is relevant to a section if its `label` or `description` directly matches or closely relates to that section’s title.  
• Mapping: For each section, iterate through all nodes; if a node is relevant, append its exact `url` (no modifications) to the section’s array.  
• Multiple URLs: Sections may list multiple URLs; nodes may map to more than one section.  
• Output: Return the outline in the same JSON format, with each section’s array filled with the matching URLs. Do not add any other fields or commentary.
"""

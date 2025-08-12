# kg.py
import os
import sys
import time
import json
import dspy
import argparse
from tqdm import tqdm
from pathlib import Path
from itertools import chain
from omegaconf import OmegaConf
from collections import defaultdict
from typing import List, Tuple, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from pipeline.apollo.src import LLM
from pipeline.apollo.src import VectorRM, Retriever
from pipeline.apollo.src.prompts.graph import PROMPTS
from pipeline.apollo.src.core.information import Information
from pipeline.apollo.src.core.information import KnowledgeBase
from pipeline.apollo.src.agents.outline_generator import OutlineGenerationAgent

from pipeline.apollo.src.utils.resolver_kg import (
    validate_knowledge_graph,
    extract_groups,
)
from pipeline.apollo.src.utils.info_diversity import eval_info_diversity_per_depth
from pipeline.apollo.src.utils.file_handler import load_json, dump_json
from pipeline.apollo.src.utils.outline_token_limit import inspect_outline_token_limit
from pipeline.apollo.src.utils.common import get_device, load_domains
from pipeline.apollo.src.utils.vizualize_kg import plot_kg
from pipeline.apollo.src.utils.logger import setup_logging, get_logger, add_file_logging

from config.paths import config_dir

setup_logging()
logger = get_logger(__name__)


def exit():
    sys.exit(0)


class Config:
    """Configuration class for the pipeline."""

    @classmethod
    def setup(
        cls,
        topic,
        base_dir="tmp",
        config_path=f"{config_dir}/apollo.yaml",
    ):
        cfg = OmegaConf.load(config_path)
        cls.cfg = cfg

        # Loads attributes whithin config.yaml
        for section_name, section_value in cfg.items():
            setattr(cls, section_name, section_value)

        cls.topic = topic
        cls.topic_name = cls.topic.replace(" ", "_")

        cls.lm_model = cls.lm.default
        cls.lm_max_tokens = cls.lm.max_tokens[cls.lm_model]

        cls.search_top_k = cls.knowledge_curation.search_top_k
        cls.retrieve_top_k = cls.knowledge_curation.retrieve_top_k

        cls.base_dir = Path(base_dir or cfg.paths.base_dir)
        # time_stamp = datetime.datetime.now().strftime("%y%m%d-%H%M%S")
        # cls.topic_dir = cls.base_dir / f"{cls.topic_name}_{time_stamp}"
        cls.topic_dir = cls.base_dir / cls.topic_name
        cls.kg_dir = cls.topic_dir / "kg"
        cls.states_dir = cls.kg_dir / "States"

        subdirs = {
            "base_dir": cls.base_dir,
            "topic_dir": cls.topic_dir,
            "kg_dir": cls.topic_dir,
            "states_dir": cls.states_dir,
        }
        for _, dir_path in subdirs.items():
            dir_path.mkdir(parents=True, exist_ok=True)


class BaseModule(dspy.Module):
    """Base class for all modules in the pipeline."""

    def __init__(
        self,
        lm: dspy.LM,
        results_dir: str,
        prompt_name: str,
        prompt_version: str,
        depth: int = 0,
        max_thread_num: int = 8,
        seed: int = None,
    ):
        super().__init__()
        self.lm = lm
        self.seed = seed
        self.prompt_name = prompt_name
        self.prompt_version = prompt_version
        self.prompt_key = f"{self.prompt_name}_{self.prompt_version}"
        self.max_thread_num = max_thread_num

        depth_str = f"depth_{depth}"
        self.output_dir: Path = Config.kg_dir / results_dir / depth_str / prompt_version
        self.output_dir.mkdir(parents=True, exist_ok=True)


class GenKG(dspy.Signature):
    """Default System Prompt"""

    topic = dspy.InputField(
        description="The topic of the knowledge graph.",
        format=str,
    )
    snippet = dspy.InputField(
        description="The snippet to extract entities and relationships from.",
        format=str,
    )
    kg_dict = dspy.OutputField(
        description="The generated knowledge graph in JSON format.",
    )


class GraphGenerator(BaseModule):

    def __init__(
        self,
        lm: dspy.LM,
        results_dir: str = "GraphGenerator",
        prompt_version: Optional[str] = "v7",
        prompt_name: Optional[str] = "gen_kg_prompt",
        max_thread_num: Optional[int] = 8,
        seed: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(
            lm=lm,
            results_dir=results_dir,
            prompt_name=prompt_name,
            prompt_version=prompt_version,
            max_thread_num=max_thread_num,
            seed=seed,
            **kwargs,
        )
        logger.info("GraphGenerator initialized!")
        self.kg_builder = dspy.Predict(GenKG)

    def forward(
        self,
        snippets: List[str],
        skip: bool = False,
        verbose: bool = False,
    ) -> Tuple[List[Dict], List[Dict]]:
        if skip:
            return [], []

        GenKG.__doc__ = PROMPTS[self.prompt_key].format(
            topic=snippets[0].title,
        )

        file_prefix = self.output_dir / self.prompt_key

        def process_snippet(i, info):
            with dspy.settings.context(lm=self.lm):
                kg_dict = self.kg_builder(
                    topic=info.title,
                    snippet=info.snippets,
                ).kg_dict
                kg_dict = validate_knowledge_graph(kg_dict)

            info_number = (getattr(info, "number", None) or i) + 1
            html_path = f"{str(file_prefix)}_snippet_{info_number}.html"
            plot_kg(kg_dict, output_file=html_path, port=8086, verbose=verbose)

            kg_group = extract_groups(kg_dict)
            json_path = f"{str(file_prefix)}_snippet_{info_number}_group.json"
            dump_json(obj=kg_group, path=json_path)

            return i, kg_dict, kg_group

        subGraphs = [None] * len(snippets)
        subGroups = [None] * len(snippets)

        with ThreadPoolExecutor(max_workers=self.max_thread_num) as executor:
            futures = [
                executor.submit(process_snippet, i, snippet)
                for i, snippet in enumerate(snippets)
            ]
            for future in as_completed(futures):
                i, kg_dict, kg_group = future.result()
                subGraphs[i] = kg_dict
                subGroups[i] = kg_group

        return subGraphs, subGroups


class GenHierarchy(dspy.Signature):
    """Default System Prompt"""

    kg = dspy.InputField(
        description="A generated knowledge graph in JSON format.",
        format=str,
    )
    kg_group = dspy.InputField(
        description="Grouped substructures from the knowledge graph based on shared parent and relation.",
        format=str,
    )
    kg_dict = dspy.OutputField(
        description="The generated knowledge graph in JSON format.",
    )


class HierarchyGenerator(BaseModule):

    def __init__(
        self,
        lm: dspy.LM,
        results_dir: str = "HierarchyGenerator",
        prompt_version: Optional[str] = "v5",
        prompt_name: Optional[str] = "build_hierarchy_kg_prompt",
        max_thread_num: Optional[int] = 8,
        seed: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(
            lm=lm,
            results_dir=results_dir,
            prompt_name=prompt_name,
            prompt_version=prompt_version,
            max_thread_num=max_thread_num,
            seed=seed,
            **kwargs,
        )
        logger.info("GraphHierarchy initialized!")
        self.kg_hierarchy = dspy.Predict(GenHierarchy)

    def forward(
        self,
        kg_for_hierarchy: List[Dict],
        kg_group: List[Dict],
        skip: bool = False,
        verbose: bool = False,
    ) -> List[Dict]:
        if skip:
            return []

        file_prefix = self.output_dir / self.prompt_key
        GenHierarchy.__doc__ = PROMPTS[self.prompt_key]

        def process_graph(i, kg_for_hierarchy, kg_group):
            if kg_group:
                with dspy.settings.context(lm=self.lm):
                    kg_hierarchy = self.kg_hierarchy(
                        kg=kg_for_hierarchy,
                        kg_group=kg_group,
                    ).kg_dict
                    kg_hierarchy = validate_knowledge_graph(kg_hierarchy)
            else:
                kg_hierarchy = kg_for_hierarchy

            html_path = f"{str(file_prefix)}_snippet_{i+1}.html"
            plot_kg(kg_hierarchy, output_file=html_path, port=8086, verbose=verbose)

            return i, kg_hierarchy

        sub_graphs_hierarchy = [None] * len(kg_for_hierarchy)

        with ThreadPoolExecutor(max_workers=self.max_thread_num) as executor:
            futures = [
                executor.submit(process_graph, i, base, group)
                for i, (base, group) in enumerate(zip(kg_for_hierarchy, kg_group))
            ]
            for future in as_completed(futures):
                i, kg_dict = future.result()
                sub_graphs_hierarchy[i] = kg_dict

        return sub_graphs_hierarchy

    def merge_subgraphs(
        self,
        graphs: List[Dict] = None,
        subgraphs_dir: str = None,
        from_checkpoint: bool = False,
        skip: bool = False,
    ) -> Dict:
        logger.info("Merging subgraphs...")
        if skip:
            return {}

        if from_checkpoint:
            load_dir = Path(self.output_dir) if from_checkpoint else Path(subgraphs_dir)
            subgraphs_paths = sorted(load_dir.glob("*.json"))
            graphs: List[Dict] = [load_json(path) for path in subgraphs_paths]
        else:
            load_dir = Path(self.output_dir)
            graphs = [(json.loads(g) if isinstance(g, str) else g) for g in graphs]

        merged_out_dir = load_dir.parent
        merged_out_dir.mkdir(parents=True, exist_ok=True)

        all_keys = {key for graph in graphs for key in graph}
        merged_graph = {
            key: list(chain.from_iterable(graph.get(key, []) for graph in graphs))
            for key in all_keys
        }
        filename = (
            merged_out_dir / f"{self.prompt_name}_{self.prompt_version}_snippet_all"
        )
        merged_html_path = str(filename.with_suffix(".html"))
        merged_json_path = str(filename.with_suffix(".json"))

        # print(f"Saving merged graph to {merged_html_path}")
        dump_json(obj=merged_graph, path=merged_json_path)
        plot_kg(merged_graph, output_file=merged_html_path, port=8086)

        return merged_graph


class AskQuestion(dspy.Signature):
    """Default System Prompt"""

    kg = dspy.InputField(
        description="A knowledge graph in JSON format.",
        format=str,
    )
    topic = dspy.InputField(
        description="The topic you want to understand.",
        format=str,
    )
    queries = dspy.OutputField(
        description="A set of NEW questions to expand the knowledge graph.",
    )


class QuestionsGenerator(BaseModule):
    def __init__(
        self,
        lm: dspy.LM,
        results_dir: str = "QuestionsGenerator",
        prompt_version: Optional[str] = "v7",
        prompt_name: Optional[str] = "expand_kg_prompt",
        max_thread_num: Optional[int] = 8,
        seed: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(
            lm=lm,
            results_dir=results_dir,
            prompt_name=prompt_name,
            prompt_version=prompt_version,
            max_thread_num=max_thread_num,
            seed=seed,
            **kwargs,
        )
        logger.info("QuestionsGenerator initialized!")
        self.question_generator = dspy.Predict(AskQuestion)

    def format_seen(self, questions: list[str]) -> str:
        if questions:
            body = "\n".join(f"   - {q}" for q in questions)
        else:
            body = "   - None yet"
        return f"```questions_already_explored\n{body}\n```"

    def forward(
        self,
        kg: Dict,
        questions_seen: List[str],
        topic: str,
        from_checkpoint=False,
        skip: bool = False,
    ) -> List[str]:
        if skip:
            return []

        graph = json.loads(kg) if isinstance(kg, str) else kg

        AskQuestion.__doc__ = PROMPTS[self.prompt_key].format(
            topic=topic,
            questions_seen=self.format_seen(questions_seen),
        )

        with dspy.settings.context(lm=self.lm):
            questions: str = self.question_generator(
                kg=graph,
                topic=topic,
            ).queries

        question_dict = json.loads(questions)
        file_prefix = self.output_dir / self.prompt_key
        question_path = f"{str(file_prefix)}_kg.json"
        dump_json(obj=question_dict, path=question_path)

        return questions

    def forward_(
        self,
        kg: List[Dict],
        questions_seen: List[str],
        topic: str,
        kg_dir: str = None,
        from_checkpoint: bool = False,
        skip: bool = False,
    ) -> List[str]:

        if skip:
            return []

        if from_checkpoint:
            load_dir = Path(kg_dir) if from_checkpoint else Path(self.output_dir)
            if isinstance(kg, str):
                graphs = [load_json(kg) for kg in kg]
        else:
            load_dir = Path(self.output_dir).parent
            if isinstance(kg, str):
                graphs = [load_json(kg)]
            elif isinstance(kg, dict):
                graphs = [kg]
            elif isinstance(kg, list):
                graphs = [json.loads(g) if isinstance(g, str) else g for g in kg]

        out_dir = load_dir / self.prompt_version
        out_dir.mkdir(parents=True, exist_ok=True)
        file_prefix = out_dir / self.prompt_key

        AskQuestion.__doc__ = PROMPTS[self.prompt_key].format(
            topic=topic,
            questions_seen=self.format_seen(questions_seen),
        )

        def process_graph(i, kg):
            with dspy.settings.context(lm=self.lm):
                questions = self.question_generator(
                    kg=kg,
                    topic=topic,
                ).queries
            return i, questions

        questions = [None] * len(graphs)

        with ThreadPoolExecutor(max_workers=self.max_thread_num) as executor:
            futures = [
                executor.submit(process_graph, i, graph)
                for i, graph in enumerate(graphs)
            ]
            for future in as_completed(futures):
                i, question = future.result()
                questions[i] = question
                question_path = f"{str(file_prefix)}_kg_{i+1}.json"

                question_dict = json.loads(question)
                dump_json(obj=question_dict, path=question_path)

        return questions


class ClusterEntities(dspy.Signature):
    """Default System Prompt"""

    entities = dspy.InputField(
        description="A list of entities to cluster.",
        format=str,
    )
    clusters = dspy.OutputField(
        description="A list of clusters, each containing a list of entities.",
    )


class NormalizeKG(BaseModule):
    def __init__(
        self,
        lm: dspy.LM,
        results_dir: str = "NormalizeKG",
        prompt_version: Optional[str] = "v4",
        prompt_name: Optional[str] = "cluster_entities_prompt",
        max_thread_num: Optional[int] = 8,
        seed: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(
            lm=lm,
            results_dir=results_dir,
            prompt_name=prompt_name,
            prompt_version=prompt_version,
            max_thread_num=max_thread_num,
            seed=seed,
            **kwargs,
        )
        logger.info("ClusterGenerator initialized!")
        self.cluster_generator = dspy.ChainOfThought(ClusterEntities)

    def normalized_kg(self, kg: dict, output_dir: str) -> dict:
        """Build clusters and update entities with canonical labels"""

        clusters = defaultdict(list)
        for node in kg["nodes"]:
            node_id = node["id"].lower()
            clusters[node_id].append(
                {
                    "id": node["id"],
                    "label": node["label"],
                    "description": node["description"],
                }
            )

        clusters_result = {"clusters": []}
        id_to_canonical = {}

        for node_id, members in clusters.items():
            if len(members) > 1:
                canonical_label = members[0]["label"]
                member_details = [
                    {"id": member["id"], "label": member["label"]} for member in members
                ]

                clusters_result["clusters"].append(
                    {"canonical_label": canonical_label, "members": member_details}
                )

                for member in members:
                    id_to_canonical[member["id"].lower()] = canonical_label

        for node in kg["nodes"]:
            node_id = node["id"].lower()
            if node_id in id_to_canonical:
                node["label"] = id_to_canonical[node_id]

        clusters_path = output_dir.replace(".json", "_clusters.json")
        updated_path = output_dir.replace(".json", "_updated.json")

        dump_json(clusters_result, clusters_path)
        dump_json(kg, updated_path)

        logger.info(f"Save clusters to: {clusters_path}")
        logger.info(f"Update KG entities to: {updated_path}")

        return kg, clusters

    def filter_entities(self, entities, clusters):
        """Filter out entities that are part of clusters"""
        cluster_ids = set()
        for cluster in clusters["clusters"]:
            cluster_ids.update(member["id"] for member in cluster["members"])
        nodes_new = [entity for entity in entities if entity["id"] not in cluster_ids]
        return nodes_new

    def apply_lm_clusters(self, kg, lm_clusters):
        """Apply LM-generated clusters to knowledge graph"""
        for cluster in lm_clusters:
            canonical_label = cluster["canonical_label"]
            for member in cluster["members"]:
                for node in kg["nodes"]:
                    if node["id"] == member["id"]:
                        node["label"] = canonical_label

    def forward(
        self,
        kg: List[Dict],
        topic: str,
        kg_dir: str = None,
        from_checkpoint: bool = False,
        skip: bool = False,
        eval_lm=False,
    ) -> List[str]:
        if skip:
            logger.info("Skipping normalization")
            return []

        normalized_kg, clusters = self.normalized_kg(kg, kg_dir)
        if not eval_lm:
            html_path = f"{str(file_prefix)}_snippet_.html"
            plot_kg(normalized_lm_kg, output_file=html_path, port=8086)
            return normalized_kg

        if from_checkpoint:
            load_dir = Path(self.output_dir).parent if from_checkpoint else Path(kg_dir)
            graphs_paths = sorted(load_dir.glob("*.json"))
            graphs: List[Dict] = [load_json(path) for path in graphs_paths]
        else:
            load_dir = Path(self.output_dir).parent
            graphs = [(json.loads(g) if isinstance(g, str) else g) for g in graphs]

        out_dir = load_dir / self.prompt_version
        file_prefix = out_dir / self.prompt_key
        file_prefix.mkdir(parents=True, exist_ok=True)

        ClusterEntities.__doc__ = PROMPTS[self.prompt_key].format(
            topic=topic,
        )

        entities = normalized_kg["nodes"]
        pruned_entities = self.filter_entities(entities, clusters)

        lm_clusters = self.cluster_generator(entities=pruned_entities).clusters
        normalized_lm_kg = self.apply_lm_clusters(normalized_kg, lm_clusters)

        html_path = f"{str(file_prefix)}_snippet_.html"
        plot_kg(normalized_lm_kg, output_file=html_path, port=8086)
        return normalized_lm_kg


class QuestionToQuery(dspy.Signature):
    """Default System Prompt"""

    topic = dspy.InputField(desc="Topic you are an expert on.")
    questions = dspy.InputField(desc="A set of questions in JSON format")
    queries = dspy.OutputField(
        desc="The queries that would be used in Google Search in JSON format.",
    )


AUDIENCE = {
    "general_public": "general public e.g. a person that does not know about the topic and wants to understand what is it about.",
    "researchers": "researches interested to get a depth understanding of the topic e.g. PhD students, Professors, among other researchers that wants to get a depth understanding of the topic treated.",
}


class ReflectQueries(BaseModule):
    def __init__(
        self,
        lm: dspy.LM,
        results_dir: str = "ReflectQueries",
        prompt_version: Optional[str] = "3",
        prompt_name: Optional[str] = "questions_to_queries_prompt",
        max_thread_num: Optional[int] = 8,
        seed: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(
            lm=lm,
            results_dir=results_dir,
            prompt_name=prompt_name,
            prompt_version=prompt_version,
            max_thread_num=max_thread_num,
            seed=seed,
            **kwargs,
        )
        logger.info("ReflectQueries initialized!")
        self.query_reflector = dspy.Predict(QuestionToQuery)

    def format_seen(self, queries: list[str]) -> str:
        if queries:
            body = "\n".join(f"   - {q}" for q in queries)
        else:
            body = "   - None yet"

        formated_str = f"```queries_already_used\n{body}\n```"
        logger.info(formated_str)
        return formated_str

    def forward(
        self,
        topic: str,
        queries_seen: List[str],
        questions: str,
        from_checkpoint: bool = False,
        skip: bool = False,
    ) -> Dict:
        if skip:
            return []

        QuestionToQuery.__doc__ = PROMPTS[self.prompt_key].format(
            queries_seen=self.format_seen(queries_seen),
            audience=AUDIENCE["researchers"],
            topic=topic,
        )

        with dspy.settings.context(lm=self.lm):
            queries = self.query_reflector(
                topic=topic,
                questions=questions,
            ).queries

        if isinstance(queries, str):
            queries_data = json.loads(queries)

        file_prefix = self.output_dir / self.prompt_key
        query_path = f"{str(file_prefix)}_queries.json"
        logger.info(f"Saving reflected queries to {query_path}")
        dump_json(obj=queries_data, path=query_path)

        queries_list = queries_data.get("combined_queries", [])
        return queries_list


class KnowledgeGraph:
    def __init__(
        self,
        lm: LLM,
        retriever: Retriever,
        max_depth: int = 4,
        config_base_dir: str = None,
    ):
        self.lm = lm
        self.retriever = retriever
        self.max_depth = max_depth
        self.current_depth = 0
        self.config_base_dir = config_base_dir

    def init_knowledge_base(self, topic):

        self.topic = topic
        self.topic_name = topic.replace(" ", "_")

        self.gather_info = {
            "topic": self.topic,
            "current_depth": 0,
            "max_depth": self.max_depth,
            "queries_by_depth": {},
            "metadata": {
                "lm_model": getattr(self.lm, "model", "unknown"),
            },
        }

        for i in range(self.max_depth + 1):
            self.gather_info["queries_by_depth"][str(i)] = []

    def save_gather_info(self):
        self.gather_info_path = Config.topic_dir / "gather_info.json"
        dump_json(obj=self.gather_info, path=self.gather_info_path)

    def save_kg_state(self, depth, kg_data):
        kg_data_path = Config.states_dir / f"kg_depth_{depth}.json"
        dump_json(obj=kg_data, path=kg_data_path)
        logger.info(f"Knowledge graph state saved to: {kg_data_path}")

    def load_kg_state(self, depth):
        kg_file = Config.states_dir / f"kg_depth_{depth}.json"
        if os.path.exists(kg_file):
            return load_json(kg_file)
        return None

    def update_gather_info_with_query(self, depth, query, results):
        """Update gather_info with a new query and its results"""
        query_data = {"query": query, "search_results": []}

        for search_result in results:
            result_data = {
                "url": getattr(search_result, "url", "unknown"),
                "description": getattr(
                    search_result, "description", "Default description"
                ),
                "snippets": getattr(search_result, "snippets", []),
                "title": getattr(search_result, "title", "Unknown Title"),
            }
            query_data["search_results"].append(result_data)

        self.gather_info["queries_by_depth"][str(depth)].append(query_data)
        self.save_gather_info()

    def print_retrieved_summary(self, depth):
        urls: list[str] = []
        for _, queries in self.gather_info["queries_by_depth"].items():
            for q in queries:
                for res in q.get("search_results", []):
                    url = res.get("url")
                    if url:
                        urls.append(url)

        if not urls:
            logger.info(f"URL stats - depth {depth} → nothing retrieved yet")
            return

        logger.info(f"URL stats - depth {depth} → total: {len(urls)}")

    def print_retrieval_timing(self, queries, total_time):
        avg_time = total_time / len(queries) if queries else 0

        logger.info(
            f"""
        === RETRIEVAL TIMING SUMMARY ===
        Total queries: {len(queries)}
        Total time: {total_time:.2f}s
        Average per query: {avg_time:.2f}s
        """
        )

    def extract_question_list(self, qdict: str) -> list[str]:
        if not qdict:
            return []

        if isinstance(qdict, str):
            qdict = json.loads(qdict)

        questions = []
        for item in qdict.get("general_queries", []):
            for key, value in item.items():
                if isinstance(value, str) and key.startswith("query"):
                    questions.append(value)

        for item in qdict.get("in_depth_queries", []):
            for key, value in item.items():
                if isinstance(value, str) and key.startswith("query"):
                    questions.append(value)

        return questions

    def process_results(self, new_results: List[Information]) -> List[Information]:
        seen_urls = set()
        for depth_str, queries_data in self.gather_info["queries_by_depth"].items():
            for query_data in queries_data:
                for result in query_data.get("search_results", []):
                    url = result.get("url", "")
                    if url:
                        seen_urls.add(url)

        updated_results = []
        for result in new_results:
            if result.url not in seen_urls:
                updated_results.append(result)
                seen_urls.add(result.url)

        return updated_results

    def process_snippets(self, snippets, depth=0, do_normalize=False):
        """Process snippets and create the knowledge graph components"""

        logger.info(
            f"\n--- [DEPTH {depth}]: Compiling KG with Information Gathered  ---\n"
        )

        # Build subgraphs per snippet
        graph_generator = GraphGenerator(
            lm=self.lm,
            prompt_version="v7",
            depth=depth,
        )
        sub_graphs, sub_groups = graph_generator.forward(
            snippets=snippets,
            skip=False,
        )

        # Build hierarchy graphs
        graph_hierarchy_generator = HierarchyGenerator(
            lm=self.lm,
            prompt_version="v8",
            depth=depth,
        )
        sub_graphs_hierarchy = graph_hierarchy_generator.forward(
            kg_for_hierarchy=sub_graphs,
            kg_group=sub_groups,
            skip=False,
        )

        # Merge subgraphs
        merged_subgraphs = graph_hierarchy_generator.merge_subgraphs(
            graphs=sub_graphs_hierarchy,
            from_checkpoint=False,
            skip=False,
        )

        # Normalize the graph
        if do_normalize:
            normalizer = NormalizeKG(
                lm=self.lm,
                prompt_version="v4",
                depth=depth,
            )
            normalized_kg = normalizer.forward(
                kg=merged_subgraphs,
                topic=self.topic,
                from_checkpoint=False,
                skip=False,
            )
            return normalized_kg

        return merged_subgraphs

    def init_seeds_kg(self):
        """Build the initial knowledge graph (depth 0)"""

        init_query = f"What is {self.topic}?"
        search_results = self.retriever(
            query=init_query,
            exclude_urls=[self.ground_truth_url],
            top_k=5,
        )
        logger.info(f"Retrieved {len(search_results)} results for initial query")
        self.update_gather_info_with_query(
            depth=0,
            query=init_query,
            results=search_results,
        )
        kg = self.process_snippets(search_results, depth=0)
        self.save_kg_state(depth=0, kg_data=kg)

    def expand_kg(self, depth=None):

        if depth is None:
            depth = self.current_depth

        current_kg = self.load_kg_state(depth)
        logger.info(
            f"Loaded KG at depth {depth}: {len(current_kg.get('nodes', []))} nodes, {len(current_kg.get('edges', []))} edges"
        )

        if current_kg is None:
            logger.info(f"No knowledge graph found at depth {depth}")
            return None

        # Generate questions
        questions_generator = QuestionsGenerator(
            lm=self.lm,
            prompt_version="v7",
            depth=depth,
        )

        kg_graph = {k: current_kg[k] for k in ("nodes", "edges")}
        questions_seen = current_kg.get("questions_seen", [])

        questions: str = questions_generator.forward(
            kg=kg_graph,
            questions_seen=questions_seen,
            topic=self.topic,
            from_checkpoint=False,
            skip=False,
        )
        new_questions: List[str] = self.extract_question_list(questions)

        if Config.ablation.outline.without_reflection:
            logger.info(
                f"Skipping query reflection due to ablation setting 'Config.ablation.outline.without_reflection': {Config.ablation.outline.without_reflection}"
            )
            queries: List[str] = new_questions
            new_queries: List[str] = []

        else:
            # Generate queries
            queries_seen = current_kg.get("queries_seen", [])
            query_reflector = ReflectQueries(
                lm=self.lm,
                prompt_version="v3",
                depth=depth,
            )
            queries: List[str] = query_reflector.forward(
                topic=self.topic,
                queries_seen=queries_seen,
                questions=questions,
                from_checkpoint=False,
                skip=False,
            )
            new_queries: List[str] = queries

        # Retrieve information for new depth
        all_snippets = []
        new_depth = depth + 1
        retrieval_start = time.time()
        for i, query in enumerate(queries, 1):
            logger.info(
                f"Retrieving information for query ({i}/{len(queries)}): {query}"
            )

            query_start = time.time()
            raw_results: List[Information] = self.retriever(
                query=query,
                exclude_urls=[self.ground_truth_url],
                top_k=Config.search_top_k,
            )
            results = self.process_results(raw_results)[: Config.retrieve_top_k]
            query_time = time.time() - query_start
            logger.info(f"Query retrieved {len(results)} results in {query_time:.2f}s")

            all_snippets.extend(results)

            self.update_gather_info_with_query(
                depth=new_depth,
                query=query,
                results=results,
            )
        total_time = time.time() - retrieval_start
        self.print_retrieval_timing(queries, total_time)

        # Create sub-graphs from the retrieved snippets
        new_kg = self.process_snippets(all_snippets, depth=new_depth)

        merged_kg = {
            "nodes": current_kg.get("nodes", []) + new_kg.get("nodes", []),
            "edges": current_kg.get("edges", []) + new_kg.get("edges", []),
            "keywords": current_kg.get("keywords", []) + new_kg.get("keywords", []),
            "questions": current_kg.get("questions", []) + new_kg.get("questions", []),
            "questions_seen": current_kg.get("questions_seen", []) + new_questions,
            "queries_seen": current_kg.get("queries_seen", []) + new_queries,
        }

        logger.info(
            f"Merged KG at depth {new_depth}: {len(merged_kg.get('nodes', []))} nodes, {len(merged_kg.get('edges', []))} edges"
        )

        self.save_kg_state(new_depth, merged_kg)
        self.current_depth = new_depth

        return merged_kg

    def build_kg(
        self,
        topic: str,
        ground_truth_url: str = "",
        max_depth=None,
        base_dir=None,
    ):

        Config.setup(
            topic=topic,
            base_dir=base_dir or self.config_base_dir,
        )
        self.init_knowledge_base(topic)
        self.ground_truth_url = ground_truth_url

        start_time_total = time.time()
        logger.info(f"Starting knowledge graph build process for topic: {self.topic}")

        timing_stats = {
            "total": 0,
            "seed_generation": 0,
            "expansions": {},
        }

        if max_depth is None:
            max_depth = self.max_depth

        # Initialize the knowledge graph if needed
        if self.current_depth == 0 and self.load_kg_state(0) is None:
            start_time = time.time()
            logger.info("Initializing seed knowledge graph (depth 0)")
            try:
                self.init_seeds_kg()
                seed_time = time.time() - start_time
                timing_stats["seed_generation"] = seed_time
                logger.info(
                    f"Completed seed knowledge graph in {seed_time:.2f} seconds"
                )
            except Exception as e:
                logger.error(f"Error initializing seed knowledge graph: {e}")
                return None

        retry_count = 0
        max_retries = 3

        while self.current_depth < max_depth:
            if Config.metrics.eval_info_diversity:
                result_eval: dict = eval_info_diversity_per_depth(
                    base_dir=Config.topic_dir,
                    max_depth=max_depth,
                    embedding_model="paraphrase-MiniLM-L6-v2",
                )
                result_eval_pretty = json.dumps(result_eval, indent=2)
                logger.info(
                    f"Evaluation Information Diversity at Depth: {self.current_depth}\n\n{result_eval_pretty}"
                )

            current_depth = self.current_depth
            next_depth = current_depth + 1

            logger.info(
                f"\n--- Expanding KG Depth: {current_depth} → {next_depth} ---\n"
            )

            start_time = time.time()
            self.print_retrieved_summary(self.current_depth)

            try:
                self.expand_kg(current_depth)
                expansion_time = time.time() - start_time
                timing_stats["expansions"][
                    f"{current_depth}→{next_depth}"
                ] = expansion_time
                logger.info(
                    f"Completed depth {next_depth} expansion in {expansion_time:.2f} seconds"
                )
                retry_count = 0
            except Exception as e:
                logger.error(
                    f"Error expanding knowledge graph at depth {current_depth}: {e}"
                )

                retry_count += 1
                if retry_count <= max_retries:
                    logger.info(
                        f"Retrying expansion at depth {current_depth} (Attempt {retry_count}/{max_retries})"
                    )
                    time.sleep(5)
                    continue
                else:
                    logger.warning(
                        f"Max retries reached for depth {current_depth}. Moving to next depth."
                    )
                    self.current_depth = next_depth
                    retry_count = 0

        # Final processing
        final_kg = self.load_kg_state(self.current_depth)
        total_time = time.time() - start_time_total
        timing_stats["total"] = total_time

        self.print_retrieved_summary(self.current_depth)
        logger.info(
            f"Completed full knowledge graph build for topic '{self.topic}' in {total_time:.2f} seconds"
        )
        logger.info(f"Final knowledge graph depth: {self.current_depth}")

        timing_path = Config.topic_dir / "timing_stats.json"
        with open(timing_path, "w") as f:
            json.dump(timing_stats, f, indent=2)

        kg = inspect_outline_token_limit(final_kg)
        kb = KnowledgeBase.from_gather_info_log_file(self.gather_info_path)

        """Generate Draft Outline"""
        # TODO: temp gen outlines here should be moved to engine.py
        try:
            outline_lm = LLM("gpt-4o-mini", max_tokens=2000, temperature=1, cache=False)
            outline_generator = OutlineGenerationAgent(lm=outline_lm)
            outline, draft_outline = outline_generator.generate_outline(
                topic=self.topic,
                kg=kg,
                return_draft_outline=True,
                output_dir=Config.topic_dir,
            )
        except Exception as e:
            logger.error(f"Error generating outline: {e}")

        return kb, kg


def main(args):

    if hasattr(args, "tmp") and args.tmp:
        add_file_logging(args.tmp, args.jobid)
        logger.info(f"Starting job with ID: {args.jobid}")

    domains = load_domains(selected_domains=getattr(args, "target_domain", None))

    for i, (domain, topics) in enumerate(
        tqdm(domains.items(), desc="Domain and topics")
    ):
        rm = VectorRM(
            collection_name=domain,
            embedding_model="Snowflake/snowflake-arctic-embed-m-v2.0",
            device=get_device(),
            k=args.top_k,
            seed=args.seed,
        )

        if getattr(args, "specific_topics", None):
            topics = [topic for topic in topics if topic in args.specific_topics]

        for j, topic in enumerate(tqdm(topics, desc="Generating articles")):
            logger.info(f"Generating article for topic '{topic}'.")

            args.base_dir = os.path.join(args.tmp, args.dataset, domain, args.jobid)

            lm = LLM(
                model=args.lm,
                max_tokens=args.max_tokens,
                temperature=1,
                cache=False,
            )

            rm.set_filter_by(topic)
            retriever = Retriever(rm=rm, max_thread=6)

            try:
                kg_manager = KnowledgeGraph(
                    lm=lm,
                    retriever=retriever,
                    max_depth=args.depth,
                    config_base_dir=args.base_dir,
                )

                kg_manager.build_kg(topic=topic)

            except Exception as e:
                logger.error(f"Error generating article for topic '{topic}': {e}")
                continue

        rm.cleanup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    args, unknown = parser.parse_known_args()
    args.dataset = "SciWiki-100"
    args.depth = 4
    args.seed = 42
    args.jobid = [
        # "0",
        # "1",
        "2",
    ][0]

    args.target_domain = [
        "ComputerScience",
        # "AgriBio",
        # "Neuro",
    ][0]

    args.specific_topics = [
        # "Carica papaya",
        # "Dopamine hypothesis of schizophrenia",
        # "Cyclic redundancy check",
        # "Ensemble learning",
        # "Linear discriminant analysis",
        "Network time protocol",
    ]
    args.use_retriever = True
    args.top_k = 10

    args.max_tokens = 16000
    args.lm = "gpt-4o-mini"
    # args.lm = "claude-3-7-sonnet"
    # args.lm = "llama-3-3-70B"

    args.disable_logger = False

    args.tmp = "temp/"

    if args.disable_logger:
        logger.disabled = True
    main(args)

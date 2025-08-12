# engine.py
import os
import json
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass, field

import dspy

from .tools.rm import Retriever
from .tools.lm import LMConfigs
from .core.interface import Engine
from .core.article import Article
from .core.callback import BaseCallbackHandler

from .utils.file_handler import FileIOHelper
from .utils.text_processing import truncate_filename
from .utils.text_processing import makeStringRed
from .utils.logger import setup_logging, get_logger

# Information Seeking
from .core.information import KnowledgeBase
from .tools.kg import KnowledgeGraph

# Outline Generation
from .agents.outline_generator import OutlineGenerationAgent

# Article Generation
from .agents.article_generator import ArticleGenerationAgent
from .agents.article_polisher import ApolloArticlePolishingAgent


setup_logging()
logger = get_logger(__name__)


class RunnerLMConfigs(LMConfigs):
    """Configurations for LLM used in different parts of APOLLO."""

    def __init__(self):

        # Information Seeking
        self.researcher_lm = None

        # Outline Generation
        self.outline_gen_lm = None

        # Article Generation
        self.article_writer_lm = None
        self.article_reviewer_lm = None
        self.article_polish_lm = None

    def set_researcher_lm(self, model: dspy.LM):
        self.researcher_lm = model

    def set_outline_gen_lm(self, model: dspy.LM):
        self.outline_gen_lm = model

    def set_article_gen_lm(self, model: dspy.LM):
        self.article_writer_lm = model

    def set_article_rev_lm(self, model: dspy.LM):
        self.article_reviewer_lm = model

    def set_article_polish_lm(self, model: dspy.LM):
        self.article_polish_lm = model


@dataclass
class RunnerArguments:
    """Arguments for controlling the APOLLO pipeline."""

    output_dir: str = field(
        metadata={"help": "Output directory for the results."},
    )
    depth: Optional[int] = field(
        default=4,
        metadata={"help": "The depth of the knowledge base."},
    )
    search_top_k: int = field(
        default=10,
        metadata={"help": "Top k search results to consider for each search query."},
    )
    retrieve_top_k: int = field(
        default=3,
        metadata={"help": "Top k collected references for each section title."},
    )
    max_thread_num: int = field(
        default=10,
        metadata={
            "help": "Maximum number of threads to use. "
            "Consider reducing it if keep getting 'Exceed rate limit' error when calling LM API."
        },
    )
    embedding_model: str = field(
        default="paraphrase-MiniLM-L6-v2",
        metadata={
            "help": "Embedding model used to store the information collected during KnowledgeCuration stage."
        },
    )
    seed: Optional[int] = field(
        default=None,
        metadata={"help": "Random seed for deterministic execution"},
    )


class Runner(Engine):

    def __init__(
        self,
        args: RunnerArguments,
        lm_configs: RunnerLMConfigs,
        rm,
        draft_dir=None,
    ):
        super().__init__(lm_configs=lm_configs)
        self.args = args
        self.lm_configs = lm_configs
        self.seed = args.seed
        self.retriever = Retriever(
            rm=rm,
            max_thread=self.args.max_thread_num,
        )
        if draft_dir is not None:
            self.draft_dir = draft_dir
        else:
            self.draft_dir = ""

        self.information_seeking_agent = KnowledgeGraph(
            lm=self.lm_configs.researcher_lm,
            retriever=self.retriever,
            max_depth=self.args.depth,
            config_base_dir=self.args.output_dir,
        )
        self.outline_generation_agent = OutlineGenerationAgent(
            lm=self.lm_configs.outline_gen_lm,
        )
        self.article_generation_agent = ArticleGenerationAgent(
            retriever=self.retriever,
            article_writer_lm=self.lm_configs.article_writer_lm,
            article_reviewer_lm=self.lm_configs.article_reviewer_lm,
            retrieve_top_k=self.args.retrieve_top_k,
            max_thread_num=self.args.max_thread_num,
        )
        self.apollo_article_polishing_agent = ApolloArticlePolishingAgent(
            article_writer_lm=self.lm_configs.article_writer_lm,
            article_polish_lm=self.lm_configs.article_polish_lm,
        )
        self.lm_configs.init_check()
        self.apply_decorators()

    def run_knowledge_curation(
        self,
        ground_truth_url: str = "",
        callback_handler: BaseCallbackHandler = None,
    ) -> Union[KnowledgeBase, KnowledgeGraph]:

        knowledge_base: KnowledgeBase
        kg: KnowledgeGraph

        knowledge_base, kg = self.information_seeking_agent.build_kg(
            topic=self.topic,
            ground_truth_url=ground_truth_url,
        )
        return knowledge_base, kg

    def run_outline_generation(
        self,
        knowledge_graph: Dict[str, Any],
        callback_handler: BaseCallbackHandler = None,
    ) -> Article:

        outline, draft_outline = self.outline_generation_agent.generate_outline(
            topic=self.topic,
            kg=knowledge_graph,
            return_draft_outline=True,
            callback_handler=callback_handler,
        )
        outline.dump_outline_to_file(
            os.path.join(self.draft_article_output_dir, "apollo_gen_outline.md")
        )
        draft_outline.dump_outline_to_file(
            os.path.join(self.draft_article_output_dir, "direct_gen_outline.md")
        )

    def run_url_outline_mapping(
        self,
        knowledge_graph: Dict[str, Any],
        outline: str,
    ):
        outline_url_mapping = self.outline_generation_agent.map_urls_to_outline(
            topic=self.topic,
            kg=knowledge_graph,
            outline=outline,
        )
        url_outline_mapping_path = os.path.join(
            self.draft_article_output_dir, "url_to_outline_mapping.json"
        )
        with open(url_outline_mapping_path, "w") as f:
            json.dump(outline_url_mapping, f, indent=4, ensure_ascii=True)

        logger.info(f"Saving url_to_outline_mapping to: {url_outline_mapping_path}")
        return outline_url_mapping

    def run_article_generation(
        self,
        outline: Article,
        knowledge_base: KnowledgeBase,
        ground_truth_url: str = "",
        callback_handler: BaseCallbackHandler = None,
    ) -> Article:

        draft_article = self.article_generation_agent.generate_article(
            topic=self.topic,
            knowledge_base=knowledge_base,
            article_with_outline=outline,
            callback_handler=callback_handler,
            article_output_dir=self.draft_article_output_dir,
            ground_truth_url=ground_truth_url,
        )
        # draft_article.dump_reference_to_file(
        #     os.path.join(self.draft_article_output_dir, "url_to_info.json")
        # )
        # article_draft_path = os.path.join(
        #     self.draft_article_output_dir, "apollo_gen_article.md"
        # )
        # draft_article.dump_article_as_plain_text(article_draft_path)
        # logger.info(f"Saving draft article to: {article_draft_path}")

        return draft_article

    def run_article_polishing(
        self, draft_article: Article, remove_duplicate: bool = False
    ) -> Article:

        polished_article = self.apollo_article_polishing_agent.polish_article(
            topic=self.topic,
            draft_article=draft_article,
            remove_duplicate=remove_duplicate,
        )

        polished_article.dump_reference_to_file(
            os.path.join(self.draft_article_output_dir, "url_to_info_polished.json")
        )
        polished_article.dump_article_as_plain_text(
            os.path.join(
                self.draft_article_output_dir, "apollo_gen_article_polished.md"
            )
        )
        logger.info(
            f"Saving polished article to: {os.path.join(self.draft_article_output_dir, 'apollo_gen_article_polished.md')}"
        )

        return polished_article

    def post_run(self):
        """
        Post-run operations, including:
        1. Dumping the run configuration.
        2. Dumping the LLM call history.
        """
        config_log = self.lm_configs.log()
        FileIOHelper.dump_json(
            config_log, os.path.join(self.article_output_dir, "run_config.json")
        )

        def custom_default(o):
            if hasattr(o, "to_dict"):
                return o.to_dict()
            try:
                return o.__dict__
            except AttributeError:
                return str(o)

        llm_call_history = self.lm_configs.collect_and_reset_lm_history()
        with open(
            os.path.join(self.article_output_dir, "llm_call_history.jsonl"), "w"
        ) as f:
            for call in llm_call_history:
                if "kwargs" in call:
                    call.pop("kwargs")
                f.write(json.dumps(call, indent=4, default=custom_default) + "\n")

    def _load_knowledge_base_from_local_fs(
        self,
        knowledge_base_local_path,
    ):
        assert os.path.exists(knowledge_base_local_path), makeStringRed(
            f"{knowledge_base_local_path} not exists. Please set --do-research argument to prepare the gather_info.json for this topic."
        )
        return KnowledgeBase.from_gather_info_log_file(knowledge_base_local_path)

    def _load_knowledge_graph_from_local_fs(
        self,
        knowledge_graph_local_path,
    ):
        assert os.path.exists(knowledge_graph_local_path), makeStringRed(
            f"{knowledge_graph_local_path} not exists. Please set --do-research argument to prepare the kg_depth_N.json for this topic."
        )
        return KnowledgeBase.from_kg_last_state_log_file(knowledge_graph_local_path)

    def _load_outline_from_local_fs(
        self,
        topic,
        outline_local_path,
        return_as_str=False,
    ):
        assert os.path.exists(outline_local_path), makeStringRed(
            f"{outline_local_path} not exists. Please set --do-generate-outline argument to prepare the apollo_gen_outline.md for this topic."
        )
        if return_as_str:
            return FileIOHelper.load_str(outline_local_path)
        else:
            return Article.from_outline_file(topic=topic, file_path=outline_local_path)

    def _load_draft_article_from_local_fs(
        self, topic, draft_article_path, url_to_info_path
    ):
        assert os.path.exists(draft_article_path), makeStringRed(
            f"{draft_article_path} not exists. Please set --do-generate-article argument to prepare the apollo_gen_article.md for this topic."
        )
        assert os.path.exists(url_to_info_path), makeStringRed(
            f"{url_to_info_path} not exists. Please set --do-generate-article argument to prepare the url_to_info.json for this topic."
        )
        article_text = FileIOHelper.load_str(draft_article_path)
        references = FileIOHelper.load_json(url_to_info_path)
        return Article.from_string(
            topic_name=topic, article_text=article_text, references=references
        )

    def run(
        self,
        topic: str,
        ground_truth_url: str = "",
        do_research: bool = True,
        do_generate_outline: bool = True,
        do_url_outline_mapping: bool = False,
        do_generate_article: bool = True,
        do_polish_article: bool = True,
        remove_duplicate: bool = False,
        callback_handler: BaseCallbackHandler = BaseCallbackHandler(),
    ):
        """

        Args:
            topic: The topic to research.
            do_research: If True, research the topic through information-seeking agent;
             if False, expect gather_info.json to exist in the output directory.
            do_generate_outline: If True, generate an outline for the topic;
             if False, expect apollo_gen_outline.md to exist in the output directory.
            do_generate_article: If True, generate a curated article for the topic;
             if False, expect apollo_gen_article.md to exist in the output directory.
            remove_duplicate: If True, remove duplicated content.
            callback_handler: A callback handler to handle the intermediate results.
        """
        assert (
            do_research
            or do_generate_outline
            or do_url_outline_mapping
            or do_generate_article
            or do_polish_article
        ), makeStringRed(
            "No action is specified. Please set at least one of --do-research, --do-generate-outline, --do_url_outline_mapping, --do-generate-article, --do-polish-article"
        )

        self.topic = topic
        self.article_dir_name = truncate_filename(
            topic.replace(" ", "_").replace("/", "_")
        )
        self.article_output_dir = os.path.join(
            self.args.output_dir, self.article_dir_name
        )
        os.makedirs(self.article_output_dir, exist_ok=True)

        self.draft_article_output_dir = os.path.join(
            self.args.output_dir, self.article_dir_name, self.draft_dir
        )
        os.makedirs(self.draft_article_output_dir, exist_ok=True)
        logger.info(f"Output directory for the article: {self.article_output_dir}")
        print(
            f"Output directory for the draft article: {self.draft_article_output_dir}"
        )

        # Stage 1: Knowledge Curation
        knowledge_base: KnowledgeBase = None
        knowledge_graph: Dict[str, Any] = None
        if do_research:
            knowledge_base, knowledge_graph = self.run_knowledge_curation(
                ground_truth_url=ground_truth_url,
                callback_handler=callback_handler,
            )

        # Stage 2: Outline Generation
        outline: Article = None
        if do_generate_outline:
            if knowledge_base is None:
                knowledge_base = self._load_knowledge_base_from_local_fs(
                    os.path.join(self.article_output_dir, "gather_info.json")
                )
            if knowledge_graph is None:
                knowledge_graph = self._load_knowledge_graph_from_local_fs(
                    os.path.join(
                        self.article_output_dir,
                        f"kg/States/kg_depth_{self.args.depth}.json",
                    )
                )
            outline = self.run_outline_generation(
                knowledge_graph=knowledge_graph,
                callback_handler=callback_handler,
            )
        if do_url_outline_mapping:
            if outline is None:
                outline: str = self._load_outline_from_local_fs(
                    topic=topic,
                    outline_local_path=os.path.join(
                        self.article_output_dir, "apollo_gen_outline.md"
                    ),
                    return_as_str=True,
                )
            if knowledge_graph is None:
                knowledge_graph = self._load_knowledge_graph_from_local_fs(
                    os.path.join(
                        self.article_output_dir,
                        f"kg/States/kg_depth_{self.args.depth}.json",
                    )
                )
            self.run_url_outline_mapping(
                knowledge_graph=knowledge_graph,
                outline=outline,
            )

        # Stage 3: Article Generation
        draft_article: Article = None
        if do_generate_article:
            if knowledge_base is None:
                knowledge_base = self._load_knowledge_base_from_local_fs(
                    os.path.join(self.article_output_dir, "gather_info.json")
                )
            if outline is None:
                outline = self._load_outline_from_local_fs(
                    topic=topic,
                    outline_local_path=os.path.join(
                        self.article_output_dir, "apollo_gen_outline.md"
                    ),
                )
            draft_article = self.run_article_generation(
                outline=outline,
                knowledge_base=knowledge_base,
                ground_truth_url=ground_truth_url,
                callback_handler=callback_handler,
            )

        # Stage 4: Article Polishing
        if do_polish_article:
            if draft_article is None:
                draft_article_path = os.path.join(
                    self.draft_article_output_dir, "apollo_gen_article.md"
                )
                url_to_info_path = os.path.join(
                    self.draft_article_output_dir, "url_to_info.json"
                )
                draft_article = self._load_draft_article_from_local_fs(
                    topic=topic,
                    draft_article_path=draft_article_path,
                    url_to_info_path=url_to_info_path,
                )
            self.run_article_polishing(
                draft_article=draft_article, remove_duplicate=remove_duplicate
            )

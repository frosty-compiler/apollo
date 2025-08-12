from typing import Union, Optional, Tuple

import json
import dspy

from ..core.agent import BaseAgent
from ..core.callback import BaseCallbackHandler
from ..core.article import Article
from ..utils.text_processing import ArticleTextProcessing
from ..prompts.outline import PROMPTS

from ..utils.logger import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

import sys
from omegaconf import OmegaConf
from config.paths import config_dir

cfg = OmegaConf.load(f"{config_dir}/apollo.yaml")


def exit():
    """Exit the program."""
    sys.exit(0)


class OutlineGenerationAgent(BaseAgent):

    def __init__(
        self,
        lm: dspy.LM,
    ):
        super().__init__(
            name="outline_generator",
            role="architect",
            lm=lm,
        )
        logger.info("OutlineGenAgent initialized!")
        # TODO: add config pipeline to load prompt version
        self.write_outline = WriteOutline(lm=self.lm)

    def generate_outline(
        self,
        topic: str,
        kg,
        callback_handler: BaseCallbackHandler = None,
        return_draft_outline=False,
        output_dir=None,
        do_refine_outline: bool = cfg.workflow.do_refine_outline,
    ):

        if callback_handler is not None:
            callback_handler.on_information_organization_start()

        raw_outline, refined_outline, direct_outline = self.write_outline(
            topic=topic,
            kg=kg,
            callback_handler=callback_handler,
        )

        article_with_raw_outline = Article.from_outline_str(
            topic=topic, outline_str=raw_outline
        )
        article_with_refined_outline = Article.from_outline_str(
            topic=topic, outline_str=refined_outline
        )
        article_with_draft_outline = Article.from_outline_str(
            topic=topic, outline_str=direct_outline
        )

        if output_dir:
            if do_refine_outline:
                refinement_metrics = self.calculate_outline_changes(
                    raw_outline, refined_outline
                )
                logger.info(
                    f"Outline refinement metrics for '{topic}': {refinement_metrics}"
                )

                article_with_raw_outline.dump_outline_to_file(
                    f"{str(output_dir)}/apollo_gen_raw_outline.md"
                )
                article_with_refined_outline.dump_outline_to_file(
                    f"{str(output_dir)}/apollo_gen_outline.md"
                )

            else:
                article_with_refined_outline = article_with_raw_outline
                article_with_refined_outline.dump_outline_to_file(
                    f"{str(output_dir)}/apollo_gen_outline.md"
                )
            print(f"Saving outline to: {str(output_dir)}/apollo_gen_outline.md")

            article_with_draft_outline.dump_outline_to_file(
                f"{str(output_dir)}/direct_gen_outline.md"
            )
            print(f"Saving draft-outline to: {str(output_dir)}/direct_gen_outline.md")

        if return_draft_outline:
            return article_with_refined_outline, article_with_draft_outline
        else:
            return article_with_refined_outline

    def calculate_outline_changes(self, raw_outline: str, refined_outline: str) -> dict:
        raw_sections = set(
            line.strip() for line in raw_outline.split("\n") if line.strip()
        )
        refined_sections = set(
            line.strip() for line in refined_outline.split("\n") if line.strip()
        )

        return {
            "sections_removed": len(raw_sections - refined_sections),
            "sections_kept": len(raw_sections & refined_sections),
            "total_raw_sections": len(raw_sections),
            "total_refined_sections": len(refined_sections),
            "reduction_percentage": (
                (len(raw_sections - refined_sections) / len(raw_sections)) * 100
                if raw_sections
                else 0
            ),
        }


class WriteOutline(dspy.Module):
    """Generate the outline for the Wikipedia page."""

    def __init__(
        self,
        lm: dspy.LM,
        prompt_name: str = "write_outline_kg",
        prompt_version: str = "v0",
    ):
        super().__init__()
        self.prompt_key = f"{prompt_name}_{prompt_version}"
        self.draft_page_outline = dspy.Predict(WriteOutlineFromTopic)
        self.write_page_outline = dspy.Predict(WriteOutlineKG)
        self.refine_page_outline = dspy.Predict(RefineOutlineKG)
        self.lm = lm

    def forward(
        self,
        topic: str,
        kg: str,
        callback_handler: BaseCallbackHandler = None,
    ):
        WriteOutlineKG.__doc__ = PROMPTS[self.prompt_key]
        RefineOutlineKG.__doc__ = PROMPTS["refine_outline_kg_v1"].format(topic=topic)

        with dspy.settings.context(lm=self.lm):
            direct_outline = ArticleTextProcessing.clean_up_outline(
                self.draft_page_outline(topic=topic).outline
            )
            if callback_handler:
                callback_handler.on_direct_outline_generation_end(
                    outline=direct_outline
                )
            raw_outline = ArticleTextProcessing.clean_up_outline(
                self.write_page_outline(topic=topic, kg=kg).outline
            )
            refined_outline = ArticleTextProcessing.clean_up_outline(
                self.refine_page_outline(topic=topic, draft_outline=raw_outline).outline
            )
            if callback_handler:
                callback_handler.on_outline_refinement_end(outline=refined_outline)

        return raw_outline, refined_outline, direct_outline


class WriteOutlineKG(dspy.Signature):
    """Based on this knowledge graph construct an outline for a Wikipedia Article that covers all the nodes and edges in the graph. The outline should be structured with headings and subheadings, and should build a comprehensive overview of the topic.
    Here is the format of your writing:
    1. Use "#" Title" to indicate section title, "##" Title" to indicate subsection title, "###" Title" to indicate subsubsection title, and so on.
    2. Do not include other information.
    3. Do not include topic name itself in the outline.
    """

    topic = dspy.InputField(
        desc="The topic you want to write",
        format=str,
    )
    kg = dspy.InputField(
        desc="The current understanding of the topic structured in a Knowledge Graph",
        format=str,
    )
    outline = dspy.OutputField(
        desc="A comprehensive outline of the topic",
        format=str,
    )


class RefineOutlineKG(dspy.Signature):
    """System Prompt"""

    topic = dspy.InputField(
        desc="The main topic of the Wikipedia article",
        format=str,
    )
    draft_outline = dspy.InputField(
        desc="The draft outline to be refined",
        format=str,
    )
    outline = dspy.OutputField(
        desc="The refined outline with improved structure and relevance",
        format=str,
    )


class WriteOutlineFromTopic(dspy.Signature):
    """Write an outline for a Wikipedia page.
    Here is the format of your writing:
    1. Use "#" Title" to indicate section title, "##" Title" to indicate subsection title, "###" Title" to indicate subsubsection title, and so on.
    2. Do not include other information.
    3. Do not include topic name itself in the outline.
    """

    topic = dspy.InputField(prefix="The topic you want to write: ", format=str)
    outline = dspy.OutputField(prefix="Write the Wikipedia page outline:\n", format=str)

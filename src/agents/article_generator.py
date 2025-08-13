import os
import sys
import copy
import logging
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

import dspy

from ..tools.rm import Retriever
from ..core.agent import BaseAgent
from ..core.article import Article
from ..core.callback import BaseCallbackHandler
from ..core.information import Information, KnowledgeBase
from ..utils.text_processing import ArticleTextProcessing
from ..utils.eval_factuality import run_eval_factuality
from ..utils.logger import setup_logging, get_logger

from ..prompts.article import PROMPTS

from omegaconf import OmegaConf
from config.paths import config_dir

cfg = OmegaConf.load(f"{config_dir}/apollo.yaml")
disable_filter = cfg.ablation.article.without_filter

setup_logging()
logger = get_logger(__name__)

# logger.setLevel(logging.DEBUG) # Enable DEBUG for development
logger.setLevel(logging.INFO) # Set to INFO for production use

# Detect if debugging is enabled
debugging = logger.getEffectiveLevel() <= logging.DEBUG


def terminate_program():
    sys.exit(0)


class ArticleGenerationAgent(BaseAgent):

    def __init__(
        self,
        retriever: Retriever,
        article_writer_lm=dspy.LM,
        article_reviewer_lm=dspy.LM,
        retrieve_top_k: int = 5,
        max_thread_num: int = 7,
        max_revision_iterations: int = 3,
        output_dir: str = "output",
    ):
        super().__init__(name="article_generator", role="writer", lm=article_writer_lm)
        self.retriever = retriever
        self.article_writer_lm = article_writer_lm
        self.article_reviewer_lm = article_reviewer_lm
        self.retrieve_top_k = retrieve_top_k
        self.max_thread_num = max_thread_num
        self.max_revision_iterations = max_revision_iterations
        self.output_dir = output_dir

        self.snippet_examiner = SnippetExaminer(
            lm=self.article_writer_lm, max_thread_num=self.max_thread_num
        )
        self.section_gen = KBToSection(lm=self.article_writer_lm)
        self.section_editor = SectionEditor(lm=self.article_writer_lm)
        self.section_reviewer = SectionReviewer(lm=self.article_reviewer_lm)

    def generate_article(
        self,
        topic: str,
        knowledge_base: KnowledgeBase,
        article_with_outline: Article,
        callback_handler: BaseCallbackHandler = None,
        article_output_dir=None,
        ground_truth_url: str = "",
        eval_factuality: bool = False,
    ) -> Article:
        self.ground_truth_url = ground_truth_url
        knowledge_base.prepare_table_for_retrieval()

        if article_with_outline is None:
            raise ValueError("article_with_outline must be provided")

        sections_to_write = article_with_outline.get_first_level_section_names()
        logger.debug(f"Sections to write: {sections_to_write}")

        if len(sections_to_write) == 0:
            section_output_dict = self.generate_section(
                topic=topic,
                section_name=topic,
                knowledge_base=knowledge_base,
                section_outline="",
                section_query=[topic],
            )
            section_output_dict_collection = [section_output_dict]
        else:
            filtered_sections = [
                section_title
                for section_title in sections_to_write
                if not (
                    section_title.lower().strip() == "introduction"
                    or section_title.lower().strip().startswith("conclusion")
                    or section_title.lower().strip().startswith("summary")
                )
            ]

            def process_section(i, section_title):
                section_query = article_with_outline.get_outline_as_list(
                    root_section_name=section_title,
                    add_hashtags=False,
                )

                section_query = [f"{topic} {query}" for query in section_query]
                queries_with_hashtags = article_with_outline.get_outline_as_list(
                    root_section_name=section_title,
                    add_hashtags=True,
                )
                section_outline = "\n".join(queries_with_hashtags)

                result = self.generate_section(
                    topic,
                    section_title,
                    knowledge_base,
                    section_outline,
                    section_query,
                )
                return i, result

            section_output_dict_collection = [None] * len(filtered_sections)

            with ThreadPoolExecutor(max_workers=self.max_thread_num) as executor:
                futures = [
                    executor.submit(process_section, i, section_title)
                    for i, section_title in enumerate(filtered_sections)
                ]
                for future in as_completed(futures):
                    try:
                        i, result = future.result()
                        section_output_dict_collection[i] = result
                    except Exception as e:
                        logger.error(f"Error in threaded section processing: {e}")
                        continue

            section_output_dict_collection = [
                x for x in section_output_dict_collection if x is not None
            ]

        draft_article = copy.deepcopy(article_with_outline)
        article = copy.deepcopy(article_with_outline)
        for section_output_dict in section_output_dict_collection:
            draft_article.update_section(
                current_section_content=section_output_dict["draft_section"],
                current_section_info_list=section_output_dict["collected_info"],
                parent_section_name=topic,
            )
            article.update_section(
                current_section_content=section_output_dict["section_content"],
                current_section_info_list=section_output_dict["collected_info"],
                parent_section_name=topic,
            )
        draft_article.post_processing()
        article.post_processing()

        draft_article_references_path = os.path.join(
            article_output_dir, "url_to_info_no_reviewer.json"
        )
        draft_article.dump_reference_to_file(draft_article_references_path)
        draft_article_path = os.path.join(
            article_output_dir, "apollo_gen_article_no_reviewer.md"
        )
        draft_article.dump_article_as_plain_text(draft_article_path)
        logger.info(f"Saving draft article w/o reviewer to: {draft_article_path}")

        article_references_path = os.path.join(article_output_dir, "url_to_info.json")
        article.dump_reference_to_file(article_references_path)
        article_path = os.path.join(article_output_dir, "apollo_gen_article.md")
        article.dump_article_as_plain_text(article_path)
        logger.info(f"Saving revised article to: {article_path}")

        if eval_factuality:
            try:
                run_eval_factuality(
                    topic=topic,
                    article_path=article_path,
                    article_references_path=article_references_path,
                    draft_article_path=draft_article_path,
                    draft_article_references_path=draft_article_references_path,
                    results_dir=article_output_dir,
                )
            except Exception as e:
                logger.error(f"Error in factuality evaluation for topic '{topic}': {e}")

        return article

    def generate_section(
        self,
        topic,
        section_name,
        knowledge_base: KnowledgeBase,
        section_outline,
        section_query,
        review_per_section: bool = False,
    ):
        collected_info: List[Information] = []
        if knowledge_base is not None:
            collected_info = knowledge_base.retrieve_information(
                queries=section_query, search_top_k=self.retrieve_top_k
            )

            if not disable_filter:
                collected_info = self.snippet_examiner(
                    topic, section_query, collected_info
                )

                if len(collected_info) < len(section_query) * self.retrieve_top_k:
                    additional_info = self.retriever(
                        query=section_query,
                        exclude_urls=[self.ground_truth_url],
                        top_k=1,
                    )
                    if additional_info:
                        logger.debug(
                            f"Retrieved {len(additional_info)} additional information items for section '{section_name}'"
                        )
                        merged = []
                        for query in section_query:
                            for info in additional_info:
                                if info.meta.get("query") == query:
                                    merged.append(info)
                            for info in collected_info:
                                if info.meta.get("query") == query:
                                    merged.append(info)
                        collected_info = merged

            collected_info = collected_info or []

        draft_section: str = self.section_gen.forward(
            topic=topic,
            outline=section_outline,
            section=section_name,
            collected_info=collected_info,
        ).section

        final_section = self._review_and_revise_section_granular(
            section_content=draft_section,
            section_name=section_name,
            topic=topic,
            collected_info=collected_info,
        )
        final_section_no_granular = ""
        if review_per_section:
            final_section_no_granular = self._review_and_revise_section(
                section_content=draft_section,
                section_name=section_name,
                topic=topic,
                collected_info=collected_info,
            )

        return {
            "section_name": section_name,
            "draft_section": draft_section,
            "section_content": final_section,
            "section_content_no_granular": final_section_no_granular,
            "collected_info": collected_info,
        }

    def _review_and_revise_section_granular(
        self,
        section_content: str,
        section_name: str,
        topic: str,
        collected_info: List[Information],
    ) -> str:
        """Review and revise section content granularly, section by section."""

        article_dict = ArticleTextProcessing.parse_article_into_dict(section_content)

        # Review each section/subsection individually
        reviewed_dict = self._review_dict_recursively(
            article_dict, topic, collected_info, section_name
        )

        # Reconstruct the content from the reviewed dictionary
        final_content = ArticleTextProcessing.reconstruct_content_from_dict(
            reviewed_dict
        )

        return final_content

    def _review_dict_recursively(
        self,
        section_dict: Dict[str, Dict],
        topic: str,
        collected_info: List[Information],
        parent_section_name: str = "",
    ) -> Dict[str, Dict]:
        """Recursively review each section and subsection."""

        reviewed_dict = {}

        for section_name, section_data in section_dict.items():
            content = section_data["content"]
            subsections = section_data["subsections"]

            logger.debug(f"{'=='*4} Reviewing section: {section_name} {'=='*4}")

            if content and content.strip():

                citations = ArticleTextProcessing.extract_citations(content)

                # Filter collected_info to only include relevant references
                relevant_info, citation_mapping = (
                    ArticleTextProcessing.filter_info_by_citations(
                        collected_info, citations
                    )
                )

                logger.debug(f"Section '{section_name}' has citations: {citations}")
                logger.debug(f"Filtered to {len(relevant_info)} relevant references")

                # Review this specific section content
                reviewed_content = self._review_single_section(
                    content=content,
                    section_name=section_name,
                    topic=topic,
                    relevant_info=relevant_info,
                    citation_mapping=citation_mapping,
                )
            else:
                reviewed_content = content

            # Recursively review subsections
            reviewed_subsections = {}
            if subsections:
                reviewed_subsections = self._review_dict_recursively(
                    subsections, topic, collected_info, section_name
                )

            reviewed_dict[section_name] = {
                "content": reviewed_content,
                "subsections": reviewed_subsections,
            }

        return reviewed_dict

    def _review_single_section(
        self,
        content: str,
        section_name: str,
        topic: str,
        relevant_info: List[Information],
        citation_mapping: Dict[int, int],
    ) -> str:
        """Review a single section with its relevant references."""

        # Remap citations in content to sequential numbering for review
        content_for_review = ArticleTextProcessing.remap_citations(
            content, citation_mapping
        )

        current_content = content_for_review
        outstanding_notes = ""

        for iteration in range(self.max_revision_iterations):
            logger.debug(
                f"Reviewing section '{section_name}' - iteration {iteration + 1}"
            )

            # Review the section
            review_result = self.section_reviewer.forward(
                topic=topic,
                section_name=section_name,
                section_content=current_content,
                collected_info=relevant_info,
                previous_feedback=outstanding_notes,
            )

            logger.debug(f"Review iteration {iteration + 1}: {review_result.verdict}")

            # If approved, remap citations back to original numbering and return
            if review_result.verdict.lower() == "approved":
                logger.info(
                    f"Section '{section_name}' approved after {iteration + 1} iterations"
                )
                final_content = ArticleTextProcessing.remap_citations_back(
                    current_content, citation_mapping
                )
                return final_content

            outstanding_notes = review_result.feedback

            # Edit the section
            edit_result = self.section_editor.forward(
                section_content=current_content,
                feedback=outstanding_notes,
                collected_info=relevant_info,
            )

            current_content = ArticleTextProcessing.clean_up_section(
                edit_result.revised_section
            )

        if debugging:
            logger.warning(
                f"Section '{section_name}' did not pass review after {self.max_revision_iterations} iterations"
            )

        final_content = ArticleTextProcessing.remap_citations_back(
            current_content, citation_mapping
        )
        return final_content

    def _review_and_revise_section(
        self,
        section_content: str,
        section_name: str,
        topic: str,
        collected_info: List[Information],
    ) -> str:
        """Review and revise section until it meets factuality standards."""
        current_content = section_content
        outstanding_notes = ""

        for iteration in range(self.max_revision_iterations):
            # Review the section
            review_result = self.section_reviewer.forward(
                topic=topic,
                section_name=section_name,
                section_content=current_content,
                collected_info=collected_info,
                previous_feedback=outstanding_notes,
            )

            logger.info(f"Review iteration {iteration + 1}: {review_result.verdict}")

            # If approved, return the current content
            if review_result.verdict.lower() == "approved":
                logger.debug(
                    f"Section '{section_name}' approved after {iteration + 1} iterations"
                )
                return current_content

            # If not approved, edit the section
            outstanding_notes = review_result.feedback
            logger.debug(f"Feedback: {review_result.feedback}")

            edit_result = self.section_editor(
                section_content=current_content,
                feedback=outstanding_notes,
                collected_info=collected_info,
            )

            current_content = ArticleTextProcessing.clean_up_section(
                edit_result.revised_section
            )

        if debugging:
            logger.warning(
                f"Section '{section_name}' did not pass review after {self.max_revision_iterations} iterations"
            )
        return current_content


class SnippetExaminer(dspy.Module):
    """Examine the snippets to check if they are relevant to the topic."""

    def __init__(
        self,
        lm: dspy.LM,
        prompt_name: str = "verifier_prompt",
        prompt_version: str = "v1",
        max_thread_num: int = 7,
    ):
        super().__init__()
        self.lm = lm
        self.prompt_key = f"{prompt_name}_{prompt_version}"
        self.evaluate_snippet = dspy.Predict(SnippetExaminerSignature)
        self.max_thread_num = max_thread_num

    def forward(
        self,
        topic: str,
        section: str,
        collected_info: List[Information],
    ) -> List[Information]:
        SnippetExaminerSignature.__doc__ = PROMPTS[self.prompt_key]

        all_snippets_with_queries = []
        for info in collected_info:
            query = info.meta.get("query", section)
            for snippet in info.snippets:
                all_snippets_with_queries.append((snippet, query))

        def process_snippet(i, query, snippet):
            try:
                with dspy.settings.context(lm=self.lm):
                    answer = self.evaluate_snippet(
                        topic=topic,
                        section=query,
                        snippet=snippet,
                    ).answer
                    is_relevant = answer.lower().strip() == "yes"
                return i, query, snippet, is_relevant
            except Exception as e:
                return i, query, snippet, False

        results = [None] * len(all_snippets_with_queries)
        with ThreadPoolExecutor(max_workers=self.max_thread_num) as executor:
            futures = [
                executor.submit(process_snippet, i, query, snippet)
                for i, (snippet, query) in enumerate(all_snippets_with_queries)
            ]

            for future in as_completed(futures):
                i, query, snippet, is_relevant = future.result()
                results[i] = (snippet, is_relevant)

        relevant_snippets = [snippet for snippet, is_relevant in results if is_relevant]
        logger.info(
            f"Snippet Examiner found {len(relevant_snippets)} relevant snippets out of {len(all_snippets_with_queries)}"
        )

        filtered_info = []
        for info in collected_info:
            relevant_info_snippets = [
                s for s in info.snippets if s in relevant_snippets
            ]
            if relevant_info_snippets:
                new_info = copy.deepcopy(info)
                new_info.snippets = relevant_info_snippets
                filtered_info.append(new_info)

        return filtered_info


class SnippetExaminerSignature(dspy.Signature):
    """Default System Prompt"""

    topic = dspy.InputField(desc="The topic of the page", format=str)
    section = dspy.InputField(desc="The section to be examined", format=str)
    snippet = dspy.InputField(desc="The snippet to examine", format=str)
    answer = dspy.OutputField(desc="A 'yes' or 'no' answer", format=str)


class KBToSection(dspy.Module):
    """Use the information collected from the knowledge base to write a section."""

    def __init__(
        self,
        lm: dspy.LM,
        prompt_name: str = "writer_prompt",
        prompt_version: str = "v5",
    ):
        super().__init__()
        self.lm = lm
        self.prompt_key = f"{prompt_name}_{prompt_version}"
        self.write_section = dspy.Predict(WriteUniqueSection)

    def forward(
        self,
        topic: str,
        outline: str,
        section: str,
        collected_info: List[Information],
    ) -> dspy.Prediction:
        WriteUniqueSection.__doc__ = PROMPTS[self.prompt_key]
        logger.debug(
            f"Writing section '{section}' for topic '{topic}' with outline:\n{outline}"
        )
        info = ""
        for idx, apollo_info in enumerate(collected_info):
            info += (
                f"The following reference MUST be used to write Section: '{apollo_info.meta.get('query', '')}'\n"
                + f"Ref: [{idx + 1}]\n"
                + "\n".join(apollo_info.snippets)
            )
            info += "\n\n"

            snippet_content = "\n".join(apollo_info.snippets)
            temp = (
                f"The following reference MUST be used to write Section: '{apollo_info.meta.get('query', '')}'\n"
                + f"Ref: [{idx + 1}]\n"
                + f"URL: {apollo_info.url}\n"
                + f"{snippet_content[:200]}...[truncated]"
                + "\n\n"
            )

            # logger.debug("Snippet:\n" + temp)

        with dspy.settings.context(lm=self.lm):
            output = self.write_section(
                topic=topic,
                outline=outline,
                info=info,
                section=section,
            )
            section: str = ArticleTextProcessing.clean_up_section(output.output)
            # print(section)
        return dspy.Prediction(section=section)


class WriteUniqueSection(dspy.Signature):
    """Default System Prompt"""

    # TODO: add some instructions for correcting repetiting urls, referencing etc
    topic = dspy.InputField(desc="The topic of the page you are writing.", format=str)
    info = dspy.InputField(desc="The collected information.", format=str)
    section = dspy.InputField(desc="The section you need to write.", format=str)
    outline = dspy.InputField(
        desc="The outline of the article we are writing.", format=str
    )
    output = dspy.OutputField(
        desc="The section with proper inline citations", format=str
    )


class SectionReviewer(dspy.Module):
    """Review generated sections for factual accuracy against references."""

    def __init__(
        self,
        lm: dspy.LM,
        prompt_name: str = "reviewer_prompt",
        prompt_version: str = "v7",
    ):
        super().__init__()
        self.lm = lm
        self.prompt_key = f"{prompt_name}_{prompt_version}"
        self.review_section_with_memory = dspy.Predict(ReviewSectionWithMemorySignature)

    def forward(
        self,
        topic: str,
        section_name: str,
        section_content: str,
        collected_info: List[Information],
        previous_feedback: str = "",
    ):
        # Prepare references for review
        references = ""
        for idx, info in enumerate(collected_info):
            # references += f"The following reference MUST be used to write Section: '{info.meta.get('query', '')}'\n"
            references += f"Ref: [{idx + 1}]\n"
            references += "\n".join(info.snippets)
            references += "\n\n"

        # print(f"Initial content for section '{section_name}':\n{section_content}")
        # print(f"References for section '{section_name}':\n{references}")

        ReviewSectionWithMemorySignature.__doc__ = PROMPTS[self.prompt_key]
        with dspy.settings.context(lm=self.lm):
            output = self.review_section_with_memory(
                topic=topic,
                section_name=section_name,
                section_content=section_content,
                references=references,
                previous_feedback=previous_feedback,
            )

        return dspy.Prediction(
            verdict=output.verdict,
            feedback=output.feedback,
        )


class ReviewSectionWithMemorySignature(dspy.Signature):
    """Review a section for factual accuracy against provided references."""

    topic = dspy.InputField(desc="The topic of the Wikipedia page", format=str)
    section_name = dspy.InputField(
        desc="The name of the section being reviewed", format=str
    )
    section_content = dspy.InputField(
        desc="The generated section content to review", format=str
    )
    references = dspy.InputField(
        desc="The reference snippets that should support all claims", format=str
    )
    previous_feedback = dspy.InputField(
        desc="The feedback given in the previous round " "(empty on the first pass)",
        format=str,
    )
    verdict = dspy.OutputField(desc="Either 'approved' or 'needs revision'", format=str)
    feedback = dspy.OutputField(
        desc="Specific feedback on what needs to be fixed if not approved", format=str
    )


class SectionEditor(dspy.Module):
    """Edit sections based on reviewer feedback to improve factual accuracy."""

    def __init__(
        self,
        lm: dspy.LM,
        prompt_name: str = "editor_prompt",
        prompt_version: str = "v5",
    ):
        super().__init__()
        self.lm = lm
        self.prompt_key = f"{prompt_name}_{prompt_version}"
        self.edit_section = dspy.Predict(EditSectionSignature)

    def forward(
        self,
        section_content: str,
        feedback: str,
        collected_info: List[Information],
    ):
        # Prepare references for editing
        references = ""
        for idx, info in enumerate(collected_info):
            references += f"Ref: [{idx + 1}]\n"
            references += "\n".join(info.snippets)
            references += "\n\n"

        temp_Ref = ""
        for idx, info in enumerate(collected_info):
            temp_Ref += f"The following reference MUST be used to write Section: '{info.meta.get('query', '')}'\n"
            temp_Ref += f"Ref: [{idx + 1}]\n"
            temp_Ref += "\n".join(info.snippets)
            temp_Ref += "\n\n"

        EditSectionSignature.__doc__ = PROMPTS[self.prompt_key]
        with dspy.settings.context(lm=self.lm):
            output = self.edit_section(
                section_content=section_content,
                feedback=feedback,
                references=references,
            )
        logger.debug(f"References:\n{temp_Ref}\n")
        logger.debug(f"Editing section content with feedback:\n{feedback}\n")
        logger.debug(f"Original section content:\n{section_content}\n")
        logger.debug(f"Revised section content:\n{output.revised_section}\n")

        return dspy.Prediction(revised_section=output.revised_section)


class EditSectionSignature(dspy.Signature):
    """Edit a section based on reviewer feedback to ensure factual accuracy."""

    section_content = dspy.InputField(
        desc="The current section content that needs revision", format=str
    )
    feedback = dspy.InputField(
        desc="Specific feedback on what needs to be fixed", format=str
    )
    references = dspy.InputField(
        desc="The reference snippets to use for corrections", format=str
    )
    revised_section = dspy.OutputField(
        desc="The revised section with all issues fixed", format=str
    )

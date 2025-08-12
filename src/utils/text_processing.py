import re
import logging
from typing import List, Dict
from ..core.information import Information
from .logger import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

logger.setLevel(logging.DEBUG)


class ArticleTextProcessing:
    @staticmethod
    def limit_word_count_preserve_newline(input_string, max_word_count):
        """
        Limit the word count of an input string to a specified maximum, while preserving the integrity of complete lines.

        The function truncates the input string at the nearest word that does not exceed the maximum word count,
        ensuring that no partial lines are included in the output. Words are defined as text separated by spaces,
        and lines are defined as text separated by newline characters.

        Args:
            input_string (str): The string to be truncated. This string may contain multiple lines.
            max_word_count (int): The maximum number of words allowed in the truncated string.

        Returns:
            str: The truncated string with word count limited to `max_word_count`, preserving complete lines.
        """

        word_count = 0
        limited_string = ""

        for word in input_string.split("\n"):
            line_words = word.split()
            for lw in line_words:
                if word_count < max_word_count:
                    limited_string += lw + " "
                    word_count += 1
                else:
                    break
            if word_count >= max_word_count:
                break
            limited_string = limited_string.strip() + "\n"

        return limited_string.strip()

    @staticmethod
    def remove_citations(s):
        """
        Removes all citations from a given string. Citations are assumed to be in the format
        of numbers enclosed in square brackets, such as [1], [2], or [1, 2], etc. This function searches
        for all occurrences of such patterns and removes them, returning the cleaned string.

        Args:
            s (str): The string from which citations are to be removed.

        Returns:
            str: The string with all citation patterns removed.
        """

        return re.sub(r"\[\d+(?:,\s*\d+)*\]", "", s)

    @staticmethod
    def parse_citation_indices(s):
        """
        Extracts citation indexes from the provided content string and returns them as a list of integers.

        Args:
            content (str): The content string containing citations in the format [number].

        Returns:
            List[int]: A list of unique citation indexes extracted from the content, in the order they appear.
        """
        matches = re.findall(r"\[\d+\]", s)
        return [int(index[1:-1]) for index in matches]

    def extract_citations(content: str) -> List[int]:
        """Extract citation numbers from content like [1], [2], etc."""
        citations = re.findall(r"\[(\d+)\]", content)
        return sorted(list(set(int(c) for c in citations)))

    @staticmethod
    def remove_uncompleted_sentences_with_citations(text):
        """
        Removes uncompleted sentences and standalone citations from the input text. Sentences are identified
        by their ending punctuation (.!?), optionally followed by a citation in square brackets (e.g., "[1]").
        Grouped citations (e.g., "[1, 2]") are split into individual ones (e.g., "[1] [2]"). Only text up to
        and including the last complete sentence and its citation is retained.

        Args:
            text (str): The input text from which uncompleted sentences and their citations are to be removed.

        Returns:
            str: The processed string with uncompleted sentences and standalone citations removed, leaving only
            complete sentences and their associated citations if present.
        """

        # Convert citations like [1, 2, 3] to [1][2][3].
        def replace_with_individual_brackets(match):
            numbers = match.group(1).split(", ")
            return " ".join(f"[{n}]" for n in numbers)

        # Deduplicate and sort individual groups of citations.
        def deduplicate_group(match):
            citations = match.group(0)
            unique_citations = list(set(re.findall(r"\[\d+\]", citations)))
            sorted_citations = sorted(
                unique_citations, key=lambda x: int(x.strip("[]"))
            )
            # Return the sorted unique citations as a string
            return "".join(sorted_citations)

        text = re.sub(r"\[([0-9, ]+)\]", replace_with_individual_brackets, text)
        text = re.sub(r"(\[\d+\])+", deduplicate_group, text)

        # Deprecated: Remove sentence without proper ending punctuation and citations.
        # Split the text into sentences (including citations).
        # sentences_with_trailing = re.findall(r'([^.!?]*[.!?].*?)(?=[^.!?]*[.!?]|$)', text)

        # Filter sentences to ensure they end with a punctuation mark and properly formatted citations
        # complete_sentences = []
        # for sentence in sentences_with_trailing:
        #     # Check if the sentence ends with properly formatted citations
        #     if re.search(r'[.!?]( \[\d+\])*$|^[^.!?]*[.!?]$', sentence.strip()):
        #         complete_sentences.append(sentence.strip())

        # combined_sentences = ' '.join(complete_sentences)

        # Check for and append any complete citations that follow the last sentence
        # trailing_citations = re.findall(r'(\[\d+\]) ', text[text.rfind(combined_sentences) + len(combined_sentences):])
        # if trailing_citations:
        #     combined_sentences += ' '.join(trailing_citations)

        # Regex pattern to match sentence endings, including optional citation markers.
        eos_pattern = r"([.!?])\s*(\[\d+\])?\s*"
        matches = list(re.finditer(eos_pattern, text))
        if matches:
            last_match = matches[-1]
            text = text[: last_match.end()].strip()

        return text

    @staticmethod
    def clean_up_citation(conv):
        for turn in conv.dlg_history:
            if "References:" in turn.agent_utterance:
                turn.agent_utterance = turn.agent_utterance[
                    : turn.agent_utterance.find("References:")
                ]
            if "Sources:" in turn.agent_utterance:
                turn.agent_utterance = turn.agent_utterance[
                    : turn.agent_utterance.find("Sources:")
                ]
            turn.agent_utterance = turn.agent_utterance.replace("Answer:", "").strip()
            try:
                max_ref_num = max(
                    [int(x) for x in re.findall(r"\[(\d+)\]", turn.agent_utterance)]
                )
            except Exception as e:
                max_ref_num = 0
            if max_ref_num > len(turn.search_results):
                for i in range(len(turn.search_results), max_ref_num + 1):
                    turn.agent_utterance = turn.agent_utterance.replace(f"[{i}]", "")
            turn.agent_utterance = (
                ArticleTextProcessing.remove_uncompleted_sentences_with_citations(
                    turn.agent_utterance
                )
            )

        return conv

    @staticmethod
    def clean_up_outline(outline, topic=""):
        output_lines = []
        current_level = 0  # To track the current section level

        for line in outline.split("\n"):
            stripped_line = line.strip()

            if topic != "" and f"# {topic.lower()}" in stripped_line.lower():
                output_lines = []

            # Check if the line is a section header
            if stripped_line.startswith("#"):
                current_level = stripped_line.count("#")
                output_lines.append(stripped_line)
            # Check if the line is a bullet point
            elif stripped_line.startswith("-"):
                subsection_header = (
                    "#" * (current_level + 1) + " " + stripped_line[1:].strip()
                )
                output_lines.append(subsection_header)

        outline = "\n".join(output_lines)

        # Remove references.
        outline = re.sub(r"#[#]? See also.*?(?=##|$)", "", outline, flags=re.DOTALL)
        outline = re.sub(r"#[#]? See Also.*?(?=##|$)", "", outline, flags=re.DOTALL)
        outline = re.sub(r"#[#]? Notes.*?(?=##|$)", "", outline, flags=re.DOTALL)
        outline = re.sub(r"#[#]? References.*?(?=##|$)", "", outline, flags=re.DOTALL)
        outline = re.sub(
            r"#[#]? External links.*?(?=##|$)", "", outline, flags=re.DOTALL
        )
        outline = re.sub(
            r"#[#]? External Links.*?(?=##|$)", "", outline, flags=re.DOTALL
        )
        outline = re.sub(r"#[#]? Bibliography.*?(?=##|$)", "", outline, flags=re.DOTALL)
        outline = re.sub(
            r"#[#]? Further reading*?(?=##|$)", "", outline, flags=re.DOTALL
        )
        outline = re.sub(
            r"#[#]? Further Reading*?(?=##|$)", "", outline, flags=re.DOTALL
        )
        outline = re.sub(r"#[#]? Summary.*?(?=##|$)", "", outline, flags=re.DOTALL)
        outline = re.sub(r"#[#]? Appendices.*?(?=##|$)", "", outline, flags=re.DOTALL)
        outline = re.sub(r"#[#]? Appendix.*?(?=##|$)", "", outline, flags=re.DOTALL)
        # clean up citation in outline
        outline = re.sub(r"\[.*?\]", "", outline)
        return outline

    @staticmethod
    def clean_up_section(text):
        """Clean up a section:
        1. Remove uncompleted sentences (usually due to output token limitation).
        2. Deduplicate individual groups of citations.
        3. Remove unnecessary summary."""

        paragraphs = text.split("\n")
        output_paragraphs = []
        summary_sec_flag = False
        for p in paragraphs:
            p = p.strip()
            if len(p) == 0:
                continue
            if not p.startswith("#"):
                p = ArticleTextProcessing.remove_uncompleted_sentences_with_citations(p)
            if summary_sec_flag:
                if p.startswith("#"):
                    summary_sec_flag = False
                else:
                    continue
            if (
                p.startswith("Overall")
                or p.startswith("In summary")
                or p.startswith("In conclusion")
            ):
                continue
            if "# Summary" in p or "# Conclusion" in p:
                summary_sec_flag = True
                continue
            output_paragraphs.append(p)

        # Join with '\n\n' for markdown format.
        return "\n\n".join(output_paragraphs)

    @staticmethod
    def update_citation_index(s, citation_map):
        """Update citation index in the string based on the citation map."""
        for original_citation in citation_map:
            s = s.replace(
                f"[{original_citation}]", f"__PLACEHOLDER_{original_citation}__"
            )
        for original_citation, unify_citation in citation_map.items():
            s = s.replace(f"__PLACEHOLDER_{original_citation}__", f"[{unify_citation}]")

        # Pattern to match consecutive identical citations like [12][12] or [12][12][12]
        def merge_duplicates(match):
            citation_num = match.group(1)
            return f"[{citation_num}]"

        # Keep replacing until no more consecutive duplicates exist
        while True:
            new_s = re.sub(r"\[(\d+)\](?:\[\1\])+", merge_duplicates, s)
            if new_s == s:
                break
            s = new_s
        return s

    @staticmethod
    def parse_article_into_dict(input_string):
        """
        Parses a structured text into a nested dictionary. The structure of the text
        is defined by markdown-like headers (using '#' symbols) to denote sections
        and subsections. Each section can contain content and further nested subsections.

        The resulting dictionary captures the hierarchical structure of sections, where
        each section is represented as a key (the section's title) mapping to a value
        that is another dictionary. This dictionary contains two keys:
        - 'content': content of the section
        - 'subsections': a list of dictionaries, each representing a nested subsection
        following the same structure.

        Args:
            input_string (str): A string containing the structured text to parse.

        Returns:
            A dictionary representing contains the section title as the key, and another dictionary
        as the value, which includes the 'content' and 'subsections' keys as described above.
        """
        lines = input_string.split("\n")
        lines = [line for line in lines if line.strip()]
        root = {"content": "", "subsections": {}}
        current_path = [(root, -1)]  # (current_dict, level)

        for line in lines:
            if line.startswith("#"):
                level = line.count("#")
                title = line.strip("# ").strip()
                new_section = {"content": "", "subsections": {}}

                # Pop from stack until find the parent level
                while current_path and current_path[-1][1] >= level:
                    current_path.pop()

                # Append new section to the nearest upper level's subsections
                current_path[-1][0]["subsections"][title] = new_section
                current_path.append((new_section, level))
            else:
                current_path[-1][0]["content"] += line + "\n"

        return root["subsections"]

    @staticmethod
    def construct_bibliography_from_url_to_info(url_to_info):
        """
        Construct a bibliography from the url_to_info dictionary

        Args:
            url_to_info (dict): A dictionary containing the information of the urls

        Returns:
            str: A string containing the bibliography
        """
        bibliography_list = []
        sorted_url_to_unified_index = dict(
            sorted(
                url_to_info["url_to_unified_index"].items(), key=lambda item: item[1]
            )
        )
        for url, index in sorted_url_to_unified_index.items():
            title = url_to_info["url_to_info"][url]["title"]
            bibliography_list.append(f"[{index}]: [{title}]() - {url}")
        bibliography_string = "\n\n".join(bibliography_list)
        return f"\n\n# References\n\n{bibliography_string}"

    @staticmethod
    def print_article_structure(article):
        """Helper function to print the structure of an article for debugging"""

        def print_node(node, level=0):
            logger.debug(
                f"{'  ' * level}- {node.section_name}: {len(node.content) if node.content else 0} chars"
            )
            for child in node.children:
                print_node(child, level + 1)

        print_node(article.root)

    @staticmethod
    def remap_citations(
        content: str,
        citation_mapping: Dict[int, int],
    ) -> str:
        """Remap citations from original numbering to sequential numbering.
        Example:
            content = "Results shown in [3] and [7]. Again [3] is crucial."
            mapping = {3: 1, 7: 2}
            new_text = ArticleTextProcessing.clean_up_section(content, mapping)
            # new_text == "Results shown in [1] and [2]. Again [1] is crucial.
        """

        def replace_citation(match):
            original_num = int(match.group(1))
            if original_num in citation_mapping:
                return f"[{citation_mapping[original_num]}]"
            return match.group(0)

        return re.sub(r"\[(\d+)\]", replace_citation, content)

    @staticmethod
    def remap_citations_back(
        content: str,
        citation_mapping: Dict[int, int],
    ) -> str:
        """Remap citations from sequential numbering back to original numbering.
        Example:
            content = "Discussion references [1] and [2]. Again [1] is key."
            mapping = {3: 1, 7: 2}
            new_text = ArticleTextProcessing.remap_citations_back(content, mapping)
            # new_text == "Discussion references [3] and [7]. Again [3] is key."
        """
        reverse_mapping = {v: k for k, v in citation_mapping.items()}

        def replace_citation(match):
            sequential_num = int(match.group(1))
            if sequential_num in reverse_mapping:
                original_num = reverse_mapping[sequential_num]
                return f"[{original_num}]"
            return match.group(0)

        result = re.sub(r"\[(\d+)\]", replace_citation, content)
        return result

    @staticmethod
    def filter_info_by_citations(
        collected_info: List[Information],
        citations: List[int],
    ) -> tuple[List[Information], Dict[int, int]]:
        """
        Filter collected_info to only include items that correspond to the citations.

        Args:
            collected_info: List of Information objects (e.g., from search results)
            citations: List of citation numbers to filter by

        Returns:
            tuple[List[Information], Dict[int, int]]:
                - filtered_info: Information objects corresponding to citations
                - citation_mapping: Maps original citation numbers to new sequential numbers

        Example:
            collected_info = [info_a, info_b, info_c, info_d]  # 4 items
            citations = [2, 4, 1]  # Want items at positions 2, 4, 1

            Returns:
            - filtered_info = [info_b, info_d, info_a]  # Items in citation order
            - citation_mapping = {2: 1, 4: 2, 1: 3}  # Original pos -> new pos
        """
        relevant_info = []
        citation_mapping = {}

        for i, citation_num in enumerate(citations):
            if 1 <= citation_num <= len(collected_info):
                relevant_info.append(collected_info[citation_num - 1])
                citation_mapping[citation_num] = i + 1

        return relevant_info, citation_mapping

    @staticmethod
    def reconstruct_content_from_dict(
        reviewed_dict: Dict[str, Dict],
    ) -> str:
        """
        Reconstruct markdown content from a hierarchical dictionary structure.

        Takes a nested dictionary representing a document structure and converts it
        into a properly formatted markdown string with hierarchical headers.

        Args:
            reviewed_dict: Dictionary where each key is a section name and each value
                          is a dict containing:
                          - 'content': str - The section's text content
                          - 'subsections': Dict - Nested subsections (same structure)

        Returns:
            str: Complete markdown document with proper heading levels and spacing

        Example:
            Input dictionary:
            {
                "Introduction": {
                    "content": "This is the intro content.",
                    "subsections": {
                        "Background": {
                            "content": "Background information here.",
                            "subsections": {}
                        }
                    }
                },
                "Conclusion": {
                    "content": "Final thoughts.",
                    "subsections": {}
                }
            }

            Output markdown:
            # Introduction
            This is the intro content.

            ## Background
            Background information here.

            # Conclusion
            Final thoughts.
        """
        content_parts = []

        def add_section_content(section_dict: Dict[str, Dict], level: int = 1):
            for section_name, section_data in section_dict.items():
                # Add section header
                header_prefix = "#" * level
                content_parts.append(f"{header_prefix} {section_name}")

                # Add section content
                if section_data["content"] and section_data["content"].strip():
                    content_parts.append(section_data["content"].strip())

                # Add subsections recursively
                if section_data["subsections"]:
                    add_section_content(section_data["subsections"], level + 1)

        add_section_content(reviewed_dict)
        return "\n\n".join(content_parts)


def truncate_filename(filename, max_length=125):
    """Truncate filename to max_length to ensure the filename won't exceed the file system limit.

    Args:
        filename: str
        max_length: int, default to 125 (usual path length limit is 255 chars)
    """

    if len(filename) > max_length:
        truncated_filename = filename[:max_length]
        logger.warning(
            f"Filename is too long. Filename is truncated to {truncated_filename}."
        )
        return truncated_filename

    return filename


def makeStringRed(message):
    return f"\033[91m {message}\033[00m"

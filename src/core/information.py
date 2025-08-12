import copy
import json
import hashlib
from abc import ABC, abstractmethod
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple, Union

from ..utils.file_handler import FileIOHelper

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


class Information:
    """Class to represent detailed information.

    Inherits from Information to include a unique identifier (URL), and extends
    it with a description, snippets, and title of the information.

    Attributes:
        description (str): Brief description.
        snippets (list): List of brief excerpts or snippets.
        title (str): The title or headline of the information.
        url (str): The unique URL (serving as UUID) of the information.
    """

    def __init__(self, url, description, snippets, title, meta=None, score=0.0):
        """Initialize the Information object with detailed attributes.

        Args:
            description (str): Detailed description.
            snippets (list): List of brief excerpts or snippet.
            title (str): The title or headline of the information.
            url (str): The unique URL serving as the identifier for the information.
        """
        self.description = description
        self.snippets = snippets
        self.title = title
        self.url = url
        self.meta = meta if meta is not None else {}
        self.citation_uuid = -1
        self.score = score

    def __hash__(self):
        return hash(
            (
                self.url,
                tuple(sorted(self.snippets)),
            )
        )

    def __eq__(self, other):
        if not isinstance(other, Information):
            return False
        return (
            self.url == other.url
            and set(self.snippets) == set(other.snippets)
            and self._meta_str() == other._meta_str()
        )

    def __lt__(self, other):
        """Define ordering for deterministic sorting."""
        if not isinstance(other, Information):
            return NotImplemented
        return self.url < other.url

    def __hash__(self):
        return int(
            self._md5_hash((self.url, tuple(sorted(self.snippets)), self._meta_str())),
            16,
        )

    def _meta_str(self):
        """Generate a string representation of relevant meta information."""
        return f"Question: {self.meta.get('question', '')}, Query: {self.meta.get('query', '')}"

    def _md5_hash(self, value):
        """Generate an MD5 hash for a given value."""
        if isinstance(value, (dict, list, tuple)):
            value = json.dumps(value, sort_keys=True)
        return hashlib.md5(str(value).encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, info_dict):
        """Create a Information object from a dictionary.
           Usage: info = Information.from_dict(apollo_info_dict)

        Args:
            info_dict (dict): A dictionary containing keys 'description', 'snippets', 'title' and 'url' corresponding to the object's attributes.

        Returns:
            Information: An instance of Information.
        """
        info = cls(
            url=info_dict["url"],
            description=info_dict["description"],
            snippets=info_dict["snippets"],
            title=info_dict["title"],
            meta=info_dict.get("meta", None),
            score=info_dict.get("score", 0.0),
        )
        info.citation_uuid = int(info_dict.get("citation_uuid", -1))
        return info

    def to_dict(self):
        return {
            "url": self.url,
            "description": self.description,
            "snippets": self.snippets,
            "title": self.title,
            "meta": self.meta,
            "citation_uuid": self.citation_uuid,
        }


class DialogueTurn:
    def __init__(
        self,
        agent_utterance: str = None,
        user_utterance: str = None,
        search_queries: Optional[List[str]] = None,
        search_results: Optional[List[Union[Information, Dict]]] = None,
    ):
        self.agent_utterance = agent_utterance
        self.user_utterance = user_utterance
        self.search_queries = search_queries
        self.search_results = search_results

        if self.search_results:
            for idx in range(len(self.search_results)):
                if type(self.search_results[idx]) == dict:
                    self.search_results[idx] = Information.from_dict(
                        self.search_results[idx]
                    )

    def log(self):
        """
        Returns a json object that contains all information inside `self`
        """
        return OrderedDict(
            {
                "agent_utterance": self.agent_utterance,
                "user_utterance": self.user_utterance,
                "search_queries": self.search_queries,
                "search_results": [data.to_dict() for data in self.search_results],
            }
        )


class InformationTable(ABC):
    """
    The InformationTable class serves as data class to store the information
    collected during KnowledgeCuration stage.
    """

    def __init__(self):
        pass

    @abstractmethod
    def retrieve_information(**kwargs):
        pass


class ApolloInformationTable(InformationTable):
    """
    The InformationTable class serves as data class to store the information
    collected during KnowledgeCuration stage.
    """

    def __init__(
        self,
        conversations=List[Tuple[str, List[DialogueTurn]]],
        embedding_model="paraphrase-MiniLM-L6-v2",
        seed=None,
    ):
        super().__init__()
        self.conversations = conversations
        self.seed = seed
        self.url_to_info: Dict[str, Information] = (
            ApolloInformationTable.construct_url_to_info(self.conversations, self.seed)
        )
        self.embedding_model = embedding_model

    @staticmethod
    def construct_url_to_info(
        conversations: List[Tuple[str, List[DialogueTurn]]],
        seed: Optional[int] = None,
    ) -> Dict[str, Information]:
        url_to_info = {}

        if seed is not None:
            conversations = sorted(conversations, key=lambda x: x[0])

        for persona, conv in conversations:
            for turn in conv:
                if seed is not None and turn.search_results:
                    turn.search_results.sort(key=lambda x: x.url)

                for apollo_info in turn.search_results:
                    if apollo_info.url in url_to_info:
                        url_to_info[apollo_info.url].snippets.extend(
                            apollo_info.snippets
                        )
                    else:
                        url_to_info[apollo_info.url] = apollo_info
        for url in url_to_info:
            url_to_info[url].snippets = list(dict.fromkeys(url_to_info[url].snippets))
            if seed is not None:
                url_to_info[url].snippets.sort()
        return url_to_info

    @staticmethod
    def construct_log_dict(
        conversations: List[Tuple[str, List[DialogueTurn]]],
    ) -> List[Dict[str, Union[str, Any]]]:
        conversation_log = []
        for persona, conv in conversations:
            conversation_log.append(
                {"perspective": persona, "dlg_turns": [turn.log() for turn in conv]}
            )
        return conversation_log

    def dump_url_to_info(self, path):
        url_to_info = copy.deepcopy(self.url_to_info)
        for url in url_to_info:
            url_to_info[url] = url_to_info[url].to_dict()
        FileIOHelper.dump_json(url_to_info, path)

    @classmethod
    def from_conversation_log_file(cls, path):
        conversation_log_data = FileIOHelper.load_json(path)
        conversations = []
        for item in conversation_log_data:
            dialogue_turns = [DialogueTurn(**turn) for turn in item["dlg_turns"]]
            persona = item["perspective"]
            conversations.append((persona, dialogue_turns))
        return cls(conversations)

    def prepare_table_for_retrieval(self):
        self.encoder = SentenceTransformer(
            self.embedding_model,
            trust_remote_code=True,
        )
        self.collected_urls = []
        self.collected_snippets = []

        for url, information in self.url_to_info.items():
            for snippet in information.snippets:
                self.collected_urls.append(url)
                self.collected_snippets.append(snippet)
        self.encoded_snippets = self.encoder.encode(
            self.collected_snippets, show_progress_bar=False
        )

    def retrieve_information(
        self, queries: Union[List[str], str], search_top_k
    ) -> List[Information]:
        selected_urls = []
        selected_snippets = []
        if type(queries) is str:
            queries = [queries]
        for query in queries:
            if (
                "snowflake" in self.embedding_model.lower()
                or "arctic" in self.embedding_model.lower()
            ):
                encoded_query = self.encoder.encode(
                    query, show_progress_bar=False, prompt_name="query"
                )
            else:
                encoded_query = self.encoder.encode(query, show_progress_bar=False)
            sim = cosine_similarity([encoded_query], self.encoded_snippets)[0]

            if hasattr(self, "seed") and self.seed is not None:
                pairs = [(sim[i], i) for i in range(len(sim))]
                pairs.sort(key=lambda x: (-x[0], x[1]))
                top_indices = [idx for _, idx in pairs[:search_top_k]]
            else:
                sorted_indices = np.argsort(sim)
                top_indices = sorted_indices[-search_top_k:][::-1]
            for i in top_indices:
                selected_urls.append(self.collected_urls[i])
                selected_snippets.append(self.collected_snippets[i])

        url_to_snippets = {}
        for url, snippet in zip(selected_urls, selected_snippets):
            if url not in url_to_snippets:
                url_to_snippets[url] = []
            if snippet not in url_to_snippets[url]:
                url_to_snippets[url].append(snippet)

        selected_url_to_info = {}
        for url in url_to_snippets:
            selected_url_to_info[url] = copy.deepcopy(self.url_to_info[url])
            if hasattr(self, "seed") and self.seed is not None:
                url_to_snippets[url].sort()
            selected_url_to_info[url].snippets = url_to_snippets[url]

        return list(selected_url_to_info.values())


class KnowledgeBase(InformationTable):

    def __init__(
        self,
        gather_info: Dict[str, Any] = None,
        # embedding_model="paraphrase-MiniLM-L6-v2",
        embedding_model="Snowflake/snowflake-arctic-embed-m-v2.0",
        seed=None,
    ):
        super().__init__()
        self.gather_info = gather_info
        self.seed = seed
        self.url_to_info: Dict[str, Information] = KnowledgeBase.construct_url_to_info(
            self.gather_info,
            # self.seed,
        )
        self.embedding_model = embedding_model

    @staticmethod
    def construct_url_to_info(
        gather_info: Dict[str, Any],
    ) -> Dict[str, Information]:

        url_to_info: Dict[str, Information] = {}
        for depth_entries in gather_info.get("queries_by_depth", {}).values():
            for entry in depth_entries:
                for res in entry.get("search_results", []):
                    url = res["url"]
                    description = res.get("description", "")
                    snippets = res.get("snippets", [])
                    title = res.get("title", "")
                    meta = res.get("meta", None)
                    score = res.get("score", 0.0)

                    if url in url_to_info:
                        url_to_info[url].snippets.extend(snippets)
                    else:
                        url_to_info[url] = Information(
                            url=url,
                            description=description,
                            snippets=list(snippets),
                            title=title,
                            meta=meta,
                            score=score,
                        )

        for info in url_to_info.values():
            info.snippets = list(dict.fromkeys(info.snippets))

        return url_to_info

    def dump_url_to_info(self, path):
        url_to_info = copy.deepcopy(self.url_to_info)
        for url in url_to_info:
            url_to_info[url] = url_to_info[url].to_dict()
        FileIOHelper.dump_json(url_to_info, path)

    @classmethod
    def from_conversation_log_file(cls, path):
        conversation_log_data = FileIOHelper.load_json(path)
        conversations = []
        for item in conversation_log_data:
            dialogue_turns = [DialogueTurn(**turn) for turn in item["dlg_turns"]]
            persona = item["perspective"]
            conversations.append((persona, dialogue_turns))
        return cls(conversations)

    @classmethod
    def from_gather_info_log_file(cls, path):
        gather_info = FileIOHelper.load_json(path)
        return cls(gather_info)

    @classmethod
    def from_kg_last_state_log_file(cls, path):
        kg = FileIOHelper.load_json(path)
        return kg

    def prepare_table_for_retrieval(self):
        self.encoder = SentenceTransformer(
            self.embedding_model,
            trust_remote_code=True,
        )
        self.collected_urls = []
        self.collected_snippets = []

        for url, information in self.url_to_info.items():
            for snippet in information.snippets:
                self.collected_urls.append(url)
                self.collected_snippets.append(snippet)
        self.encoded_snippets = self.encoder.encode(
            self.collected_snippets, show_progress_bar=False
        )

    def retrieve_information(
        self, queries: Union[List[str], str], search_top_k
    ) -> List[Information]:
        """
        Modified retrieve_information method that properly stores the query used
        to retrieve each snippet in the Information object's metadata.
        """
        selected_urls = []
        selected_snippets = []
        snippet_to_query = {}  # Track which query was used for each snippet

        if type(queries) is str:
            queries = [queries]

        for query in queries:
            if (
                "snowflake" in self.embedding_model.lower()
                or "arctic" in self.embedding_model.lower()
            ):
                encoded_query = self.encoder.encode(
                    query, show_progress_bar=False, prompt_name="query"
                )
            else:
                encoded_query = self.encoder.encode(query, show_progress_bar=False)
            sim = cosine_similarity([encoded_query], self.encoded_snippets)[0]

            if hasattr(self, "seed") and self.seed is not None:
                pairs = [(sim[i], i) for i in range(len(sim))]
                pairs.sort(key=lambda x: (-x[0], x[1]))
                top_indices = [idx for _, idx in pairs[:search_top_k]]
            else:
                sorted_indices = np.argsort(sim)
                top_indices = sorted_indices[-search_top_k:][::-1]

            for i in top_indices:
                selected_urls.append(self.collected_urls[i])
                selected_snippets.append(self.collected_snippets[i])
                # Track which query was used for this snippet
                snippet_to_query[self.collected_snippets[i]] = query

        # Group snippets by URL
        url_to_snippets = {}
        url_to_query = {}  # Track which query was used for each URL

        for url, snippet in zip(selected_urls, selected_snippets):
            if url not in url_to_snippets:
                url_to_snippets[url] = []
                url_to_query[url] = snippet_to_query[
                    snippet
                ]  # Use the query for this snippet
            if snippet not in url_to_snippets[url]:
                url_to_snippets[url].append(snippet)

        # Create the Information objects with proper metadata
        selected_url_to_info = {}
        for url in url_to_snippets:
            # Copy the original Information object
            selected_url_to_info[url] = copy.deepcopy(self.url_to_info[url])

            # Update snippets
            if hasattr(self, "seed") and self.seed is not None:
                url_to_snippets[url].sort()
            selected_url_to_info[url].snippets = url_to_snippets[url]

            # Set the query in metadata
            if selected_url_to_info[url].meta is None:
                selected_url_to_info[url].meta = {}
            selected_url_to_info[url].meta["query"] = url_to_query[url]

        return list(selected_url_to_info.values())

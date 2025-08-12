import os

os.environ["TOKENIZERS_PARALLELISM"] = "true"

import concurrent.futures
from typing import Union, List, Callable
from collections import defaultdict

import dspy
import requests

from langchain_qdrant import Qdrant
from qdrant_client import QdrantClient, models
from langchain_huggingface import HuggingFaceEmbeddings

from ..core.information import Information
from ..utils.text_processing import ArticleTextProcessing
from ..utils.logger import setup_logging, get_logger


setup_logging()
logger = get_logger(__name__)

import warnings

warnings.filterwarnings(
    "ignore",
    message=".*The class `Qdrant` was deprecated.*",
)

class BraveRM(dspy.Retrieve):
    def __init__(
        self, brave_search_api_key=None, k=3, is_valid_source: Callable = None
    ):
        super().__init__(k=k)
        if not brave_search_api_key and not os.environ.get("BRAVE_API_KEY"):
            raise RuntimeError(
                "You must supply brave_search_api_key or set environment variable BRAVE_API_KEY"
            )
        elif brave_search_api_key:
            self.brave_search_api_key = brave_search_api_key
        else:
            self.brave_search_api_key = os.environ["BRAVE_API_KEY"]
        self.usage = 0

        # If not None, is_valid_source shall be a function that takes a URL and returns a boolean.
        if is_valid_source:
            self.is_valid_source = is_valid_source
        else:
            self.is_valid_source = lambda x: True

    def get_usage_and_reset(self):
        usage = self.usage
        self.usage = 0

        return {"BraveRM": usage}

    def forward(
        self,
        query_or_queries: Union[str, List[str]],
        exclude_urls: List[str] = [],
    ):
        """Search with api.search.brave.com for self.k top passages for query or queries

        Args:
            query_or_queries (Union[str, List[str]]): The query or queries to search for.
            exclude_urls (List[str]): A list of urls to exclude from the search results.

        Returns:
            a list of Dicts, each dict has keys of 'description', 'snippets' (list of strings), 'title', 'url'
        """
        queries = (
            [query_or_queries]
            if isinstance(query_or_queries, str)
            else query_or_queries
        )
        self.usage += len(queries)
        collected_results = []
        for query in queries:
            try:
                headers = {
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": self.brave_search_api_key,
                }
                response = requests.get(
                    f"https://api.search.brave.com/res/v1/web/search?result_filter=web&q={query}",
                    headers=headers,
                ).json()
                results = response.get("web", {}).get("results", [])

                if exclude_urls:
                    results = [r for r in results if r.get("url") not in exclude_urls]

                for result in results[: self.k]:
                    collected_results.append(
                        {
                            "snippets": result.get("extra_snippets", []),
                            "title": result.get("title"),
                            "url": result.get("url"),
                            "description": result.get("description"),
                        }
                    )
            except Exception as e:
                logger.error(f"Error occurs when searching query {query}: {e}")

        return collected_results


class YouRM(dspy.Retrieve):
    def __init__(self, ydc_api_key=None, k=3, is_valid_source: Callable = None):
        super().__init__(k=k)
        if not ydc_api_key and not os.environ.get("YDC_API_KEY"):
            raise RuntimeError(
                "You must supply ydc_api_key or set environment variable YDC_API_KEY"
            )
        elif ydc_api_key:
            self.ydc_api_key = ydc_api_key
        else:
            self.ydc_api_key = os.environ["YDC_API_KEY"]
        self.usage = 0

        # If not None, is_valid_source shall be a function that takes a URL and returns a boolean.
        if is_valid_source:
            self.is_valid_source = is_valid_source
        else:
            self.is_valid_source = lambda x: True

    def get_usage_and_reset(self):
        usage = self.usage
        self.usage = 0

        return {"YouRM": usage}

    def forward(
        self, query_or_queries: Union[str, List[str]], exclude_urls: List[str] = []
    ):
        """Search with You.com for self.k top passages for query or queries

        Args:
            query_or_queries (Union[str, List[str]]): The query or queries to search for.
            exclude_urls (List[str]): A list of urls to exclude from the search results.

        Returns:
            a list of Dicts, each dict has keys of 'description', 'snippets' (list of strings), 'title', 'url'
        """
        queries = (
            [query_or_queries]
            if isinstance(query_or_queries, str)
            else query_or_queries
        )
        self.usage += len(queries)
        collected_results = []
        for query in queries:
            try:
                headers = {"X-API-Key": self.ydc_api_key}
                results = requests.get(
                    f"https://api.ydc-index.io/search?query={query}",
                    headers=headers,
                ).json()

                authoritative_results = []
                for r in results["hits"]:
                    if self.is_valid_source(r["url"]) and r["url"] not in exclude_urls:
                        authoritative_results.append(r)
                if "hits" in results:
                    collected_results.extend(authoritative_results[: self.k])
            except Exception as e:
                logger.error(f"Error occurs when searching query {query}: {e}")

        return collected_results


class VectorRM(dspy.Retrieve):
    """Retrieve information from custom documents using Qdrant.

    To be compatible with APOLLO, the custom documents should have the following fields:
        - content: The main text content of the document.
        - title: The title of the document.
        - url: The URL of the document. APOLLO use url as the unique identifier of the document, so ensure different
            documents have different urls.
        - description (optional): The description of the document.
    The documents should be stored in a CSV file.
    """

    def __init__(
        self,
        collection_name: str,
        embedding_model: str,
        device: str = "mps",
        k: int = 3,
        seed: int = None,
        query_prefix: str = "query:",
    ):
        """
        Params:
            collection_name: Name of the Qdrant collection.
            embedding_model: Name of the Hugging Face embedding model.
            device: Device to run the embeddings model on, can be "mps", "cuda", "cpu".
            k: Number of top chunks to retrieve.
            seed: Seed for deterministic behavior.
            query_prefix: Prefix to add to the query before embedding.
        """
        super().__init__(k=k)
        self.seed = seed
        self.usage = 0
        self.query_prefix = query_prefix
        self.embedding_model = embedding_model
        self.filter_condition = None

        if not collection_name:
            raise ValueError("Please provide a collection name.")
        if not embedding_model:
            raise ValueError("Please provide an embedding model.")

        model_kwargs = {"device": device, "trust_remote_code": True}
        encode_kwargs = {"normalize_embeddings": True}
        self.model = HuggingFaceEmbeddings(
            model_name=embedding_model,
            model_kwargs=model_kwargs,
            encode_kwargs=encode_kwargs,
        )

        self.collection_name = collection_name
        self.client = None
        self.qdrant = None
        self.cache = {}

        if self.seed is not None:
            logger.info(f"Initializing deterministic VectorRM with seed {self.seed}")
            self._make_deterministic()

        self.init_docker_qdrant()

    def set_filter_by(self, title: str):
        """
        Creates a filter condition for searching documents by title.

        Args:
            title (str): The title to filter by when retrieving documents.
        """

        if title:
            self.filter_condition = models.Filter(
                must=[
                    models.FieldCondition(
                        key="metadata.title",
                        match=models.MatchValue(value=title),
                    )
                ]
            )

    def _check_collection(self):
        """
        Check if the Qdrant collection exists and create it if it does not.
        """
        if self.client is None:
            raise ValueError("Qdrant client is not initialized.")
        if self.client.collection_exists(collection_name=f"{self.collection_name}"):
            logger.info(
                f"Collection '{self.collection_name}' exists. Loading the collection..."
            )
            self.qdrant = Qdrant(
                client=self.client,
                collection_name=self.collection_name,
                embeddings=self.model,
            )
        else:
            raise ValueError(
                f"Collection {self.collection_name} does not exist. Please create the collection first."
            )

    def init_docker_qdrant(self):
        """Initialize the Qdrant client that is connected to a Docker instance."""
        import docker

        client_name = "qdrant"

        try:
            docker_client = docker.from_env()
            container = docker_client.containers.get(client_name)

            if container.status != "running":
                logger.info(f"Starting Docker container: {client_name}")
                container.start()
            else:
                logger.info(
                    f"Apollo: Docker container '{client_name}' is already running."
                )

            self.client = QdrantClient("localhost", port=6333)
            self.search_params = models.SearchParams(
                quantization=models.QuantizationSearchParams(
                    ignore=False,
                    rescore=True,
                    oversampling=1.0,
                )
            )
            self._check_collection()

        except docker.errors.NotFound:
            raise ValueError(
                f"Docker container '{client_name}' not found. Please create it first."
            )
        except Exception as e:
            raise ValueError(f"Error initializing Qdrant Docker container: {e}")

    def init_offline_vector_db(self, vector_store_path: str):
        """
        Initialize the Qdrant client that is connected to an offline vector store with the given vector store folder path.

        Args:
            vector_store_path (str): Path to the vector store.
        """
        if vector_store_path is None:
            raise ValueError("Please provide a folder path.")

        try:
            self.client = QdrantClient(path=vector_store_path)
            self.search_params = None
            self._check_collection()
        except Exception as e:
            raise ValueError(f"Error occurs when loading the vector store: {e}")

    def get_usage_and_reset(self):
        usage = self.usage
        self.usage = 0

        return {"VectorRM": usage}

    def cleanup(self):
        """Release resources when done with this retriever."""
        self.client = None
        self.qdrant = None
        self.filter_condition = None

        self.model = None

        import gc

        gc.collect()

        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def get_vector_count(self):
        """
        Get the count of vectors in the collection.

        Returns:
            int: Number of vectors in the collection.
        """
        return self.qdrant.client.count(collection_name=self.collection_name)

    def _make_deterministic(self):
        """Configure the retriever for deterministic behavior."""
        import types

        if not hasattr(self, "_original_forward"):
            self._original_forward = self.forward

        def deterministic_forward(self, query_or_queries, exclude_urls=None):
            """Deterministic version of the retrieval method."""
            queries = (
                [query_or_queries]
                if isinstance(query_or_queries, str)
                else query_or_queries
            )
            queries = sorted(queries)
            self.usage += len(queries)

            collected_results = []
            for query in queries:
                if (
                    "snowflake" in self.embedding_model.lower()
                    or "arctic" in self.embedding_model.lower()
                ):
                    if not query.strip():
                        logger.info("Empty query received!")
                    query = self.query_prefix + query

                if self.qdrant is None:
                    logger.warning("Qdrant is not initialized")
                    continue

                if self.filter_condition:
                    related_docs = self.qdrant.similarity_search_with_score(
                        query=query,
                        k=self.k,
                        filter=self.filter_condition,
                        search_params=self.search_params,
                    )
                else:
                    related_docs = self.qdrant.similarity_search_with_score(
                        query,
                        k=self.k,
                        search_params=self.search_params,
                    )

                related_docs = sorted(
                    related_docs, key=lambda x: (-x[1], x[0].metadata.get("url", ""))
                )

                for doc, score in related_docs:
                    result = {
                        "description": doc.metadata.get("description", ""),
                        "snippets": [doc.page_content],
                        "title": doc.metadata.get("title", ""),
                        "url": doc.metadata.get("url", ""),
                        "score": score,
                    }
                    collected_results.append(result)
            return collected_results

        self.forward = types.MethodType(deterministic_forward, self)

    def forward(
        self,
        query_or_queries: Union[str, List[str]],
        exclude_urls: List[str],
    ) -> List[dict]:
        """
        Search in your data for self.k top passages for query or queries.

        Args:
            query_or_queries (Union[str, List[str]]): The query or queries to search for.
            exclude_urls (List[str]): Dummy parameter to match the interface. Does not have any effect.

        Returns:
            a list of Dicts, each dict has keys of 'description', 'snippets' (list of strings), 'title', 'url'
        """
        queries = (
            [query_or_queries]
            if isinstance(query_or_queries, str)
            else query_or_queries
        )
        self.usage += len(queries)
        collected_results = []

        for query in queries:
            if (
                "snowflake" in self.embedding_model.lower()
                or "arctic" in self.embedding_model.lower()
            ):
                if not query.strip():
                    logger.info("Empty query received!")
                query = self.query_prefix + query

            if self.filter_condition:
                related_docs = self.qdrant.similarity_search_with_score(
                    query=query,
                    k=self.k,
                    filter=self.filter_condition,
                    search_params=self.search_params,
                )
            else:
                related_docs = self.qdrant.similarity_search_with_score(
                    query,
                    k=self.k,
                    search_params=self.search_params,
                )

            for doc, score in related_docs:
                result = {
                    "description": doc.metadata.get("description", ""),
                    "snippets": [doc.page_content],
                    "title": doc.metadata.get("title", ""),
                    "url": doc.metadata.get("url", ""),
                    "score": score,
                }
                collected_results.append(result)

        return collected_results


class Retriever:
    """
    An abstract base class for retriever modules. It provides a template for retrieving information based on a query.
    """

    def __init__(self, rm: dspy.Retrieve, max_thread: int = 1):
        self.max_thread = max_thread
        self.rm = rm
        self._default_k = rm.k

    def collect_and_reset_rm_usage(self):
        combined_usage = []
        if hasattr(getattr(self, "rm"), "get_usage_and_reset"):
            combined_usage.append(getattr(self, "rm").get_usage_and_reset())

        name_to_usage = {}
        for usage in combined_usage:
            for model_name, query_cnt in usage.items():
                if model_name not in name_to_usage:
                    name_to_usage[model_name] = query_cnt
                else:
                    name_to_usage[model_name] += query_cnt

        return name_to_usage

    def __call__(self, *args, top_k: int = None, **kwargs):
        self.rm.k = top_k if top_k is not None else self._default_k
        return self.retrieve(*args, **kwargs)

    def retrieve(
        self,
        query: Union[str, List[str]],
        exclude_urls: List[str] = [],
    ) -> List[Information]:
        """
        Retrieve information based on a query, optionally filtered by topic/concept.

        Args:
            query: The query or list of queries
            exclude_urls: URLs to exclude from results

        Returns:
            List of Information objects
        """
        queries = query if isinstance(query, list) else [query]
        to_return = []

        def process_query(q):
            retrieved_data_list = self.rm(
                query_or_queries=[q],
                exclude_urls=exclude_urls,
            )
            local_to_return = []
            for data in retrieved_data_list:
                for i in range(len(data["snippets"])):
                    data["snippets"][i] = ArticleTextProcessing.remove_citations(
                        data["snippets"][i]
                    )
                apollo_info = Information.from_dict(data)
                apollo_info.meta["query"] = q
                local_to_return.append(apollo_info)
            return local_to_return

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_thread
        ) as executor:
            results = list(executor.map(process_query, queries))

        for result in results:
            to_return.extend(result)

        return to_return

    def print_results(self, search_results):
        """Print the search results, grouping by query."""
        # Group by the original query
        results_by_query = defaultdict(list)
        for info in search_results:
            q = info.meta.get("query", "No query provided")
            results_by_query[q].append(info)

        for query, infos in results_by_query.items():
            print("\n" + "=" * 40)
            print(f"Query: {query}")
            print("=" * 40)
            for i, info in enumerate(infos, start=1):
                print(f"\nResult {i}:")
                print("  Title  :", info.title)
                print("  URL    :", info.url)
                print("  Score  :", info.score)
                print("  Snippet:", info.snippets)
            print("\n")  # extra spacing between queries

    def save_results_txt(self, search_results, file_path):
        """Save search_results to a plain-text file, grouping by query."""
        results_by_query = defaultdict(list)
        for info in search_results:
            q = info.meta.get("query", "No query provided")
            results_by_query[q].append(info)

        with open(file_path, "w", encoding="utf-8") as f:
            for query, infos in results_by_query.items():
                f.write("=" * 40 + "\n")
                f.write(f"Query: {query}\n")
                f.write("=" * 40 + "\n\n")

                for i, info in enumerate(infos, start=1):
                    f.write(f"Result {i}:\n")
                    f.write(f"  Title  : {info.title}\n")
                    f.write(f"  URL    : {info.url}\n")
                    f.write(f"  Score  : {info.score}\n")
                    snippets = info.snippets
                    if isinstance(snippets, (list, tuple)):
                        snippets = " ".join(snippets)
                    f.write(f"  Snippet: {snippets}\n\n")

        logger.info(f"Saved results for {len(results_by_query)} queries to {file_path}")

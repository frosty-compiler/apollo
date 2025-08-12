import time
import functools
from abc import ABC, abstractmethod
from typing import Optional

from .article import BaseArticle
from .information import InformationTable
from ..tools.lm import LMConfigs
from ..utils.logger import setup_logging, get_logger


setup_logging()
logger = get_logger(__name__)


class Engine(ABC):
    def __init__(self, lm_configs: LMConfigs):
        self.lm_configs = lm_configs
        self.time = {}
        self.lm_cost = {}
        self.rm_cost = {}

    def log_execution_time_and_lm_rm_usage(self, func):
        """Decorator to log the execution time, language model usage, and retrieval model usage of a function."""

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()
            execution_time = end_time - start_time
            self.time[func.__name__] = execution_time
            logger.info(f"{func.__name__} executed in {execution_time:.4f} seconds")
            self.lm_cost[func.__name__] = self.lm_configs.collect_and_reset_lm_usage()
            if hasattr(self, "retriever"):
                self.rm_cost[func.__name__] = (
                    self.retriever.collect_and_reset_rm_usage()
                )
            return result

        return wrapper

    def apply_decorators(self):
        """Apply decorators to methods that need them."""
        methods_to_decorate = [
            method_name
            for method_name in dir(self)
            if callable(getattr(self, method_name)) and method_name.startswith("run_")
        ]
        for method_name in methods_to_decorate:
            original_method = getattr(self, method_name)
            decorated_method = self.log_execution_time_and_lm_rm_usage(original_method)
            setattr(self, method_name, decorated_method)

    @abstractmethod
    def run_knowledge_curation(self, **kwargs) -> Optional[InformationTable]:
        pass

    @abstractmethod
    def run_outline_generation(self, **kwarg) -> BaseArticle:
        pass

    @abstractmethod
    def run_article_generation(self, **kwarg) -> BaseArticle:
        pass

    @abstractmethod
    def run_article_polishing(self, **kwarg) -> BaseArticle:
        pass

    @abstractmethod
    def run(self, **kwargs):
        pass

    def summary(self):
        logger.info("***** Execution time *****")
        for k, v in self.time.items():
            logger.info(f"{k}: {v:.4f} seconds")

        logger.info("***** Token usage of language models: *****")
        for k, v in self.lm_cost.items():
            logger.info(f"{k}")
            for model_name, tokens in v.items():
                logger.info(f"    {model_name}: {tokens}")

        logger.info("***** Number of queries of retrieval models: *****")
        for k, v in self.rm_cost.items():
            logger.info(f"{k}: {v}")

    def reset(self):
        self.time = {}
        self.lm_cost = {}
        self.rm_cost = {}

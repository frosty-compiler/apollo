# lm.py
import os
import copy
import logging
import threading
from abc import ABC
from collections import OrderedDict
from typing import Optional, Literal

import dspy

logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)


class LLM(dspy.LM):
    """Language class Manager to initialize Azure or Bedrock models"""

    BEDROCK_MODEL_CONFIGS = {
        "llama-3-1-8B": {
            "model": "meta.llama3-1-8b-instruct-v1:0",
            "aws_region_name": "us-west-2",
        },
        "llama-3-3-70B": {
            "model": "us.meta.llama3-3-70b-instruct-v1:0",
            "aws_region_name": "us-west-2",
        },
        "llama-3-1-70B": {
            "model": "meta.llama3-1-70b-instruct-v1:0",
            "aws_region_name": "us-west-2",
        },
        "llama-3-70B": {
            "model": "meta.llama3-70b-instruct-v1:0",
            "aws_region_name": "us-west-2",
        },
        "mistral-7b-v2": {
            "model": "mistral.mistral-7b-instruct-v0:2",
            "aws_region_name": "us-west-2",
        },
        "claude-3-5-sonnet": {
            "model": "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "aws_region_name": "us-west-2",
        },
        "claude-3-7-sonnet": {
            "model": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
            "aws_region_name": "us-west-2",
        },
    }

    AZURE_CONFIG = {
        "api_version": os.getenv("AZURE_API_VERSION"),
        "model_versions": {
            "gpt-4o-mini": "2024-02-15-preview",
            "gpt-4o": "2024-12-01-preview",
        },
    }

    def __init__(
        self,
        model: str,
        provider: Optional[Literal["azure", "bedrock"]] = None,
        # Azure-specific parameters
        api_base: Optional[str] = None,
        api_version: Optional[str] = None,
        api_key: Optional[str] = None,
        deployment_name: Optional[str] = None,
        # Bedrock-specific parameters
        aws_region_name: Optional[str] = "us-west-2",
        aws_profile_name: Optional[str] = "USERNAME",
        # Common parameters
        model_type: Literal["chat", "text"] = "chat",
        **kwargs,
    ):
        if model is None:
            raise ValueError("Model must be specified")
        if provider is None:
            provider = self._detect_provider(model)

        self.provider = provider
        self._token_usage_lock = threading.Lock()
        self.prompt_tokens = 0
        self.completion_tokens = 0

        if provider == "azure":
            api_key = api_key or os.getenv("AZURE_API_KEY")
            api_base = api_base or os.getenv("AZURE_API_BASE")
            api_version = (
                api_version
                or self.AZURE_CONFIG["model_versions"].get(deployment_name)
                or self.AZURE_CONFIG["model_versions"].get(model)
                or self.AZURE_CONFIG["api_version"]
            )
            model_identifier = (
                f"azure/{deployment_name}" if deployment_name else f"azure/{model}"
            )
            self.model_name = deployment_name or model

            azure_defaults = {
                "top_p": 0.9,
                "frequency_penalty": 0,
                "presence_penalty": 0,
                "n": 1,
                "max_tokens": 2000,
                "cache": False,
            }
            kwargs = {**azure_defaults, **kwargs}

            super().__init__(
                model=model_identifier,
                api_base=api_base,
                api_version=api_version,
                api_key=api_key,
                model_type=model_type,
                **kwargs,
            )

        elif provider == "bedrock":

            if model in self.BEDROCK_MODEL_CONFIGS:
                config = self.BEDROCK_MODEL_CONFIGS[model]
                bedrock_model = config["model"]
                aws_region_name = config["aws_region_name"]
            else:
                bedrock_model = model

            model_identifier = f"bedrock/{bedrock_model}"
            self.model_name = bedrock_model

            bedrock_defaults = {
                "top_p": 0.9,
                "n": 1,
                "cache": False,
            }
            kwargs = {**bedrock_defaults, **kwargs}

            super().__init__(
                model=model_identifier,
                aws_region_name=aws_region_name,
                aws_profile_name=aws_profile_name,
                model_type=model_type,
                **kwargs,
            )

        else:
            raise ValueError(
                f"Provider {provider} not supported. Choose 'azure' or 'bedrock'."
            )

    def _detect_provider(self, model: str) -> str:
        """
        Automatically detect the provider based on the model name.

        Args:
            model: The model name/identifier

        Returns:
            str: Either "azure" or "bedrock"
        """
        if model in self.AZURE_CONFIG["model_versions"]:
            return "azure"

        if model in self.BEDROCK_MODEL_CONFIGS:
            return "bedrock"

        raise ValueError(
            f"Model '{model}' not supported. Supported models: {list(self.AZURE_CONFIG['model_versions'].keys()) + list(self.BEDROCK_MODEL_CONFIGS.keys())}"
        )

    def log_usage(self, response):
        """Log the total tokens from the API response."""
        try:
            if hasattr(self, "history") and self.history:
                last_call = self.history[-1]
                usage_data = last_call.get("usage")

                if usage_data:
                    with self._token_usage_lock:
                        self.prompt_tokens += usage_data.get("prompt_tokens", 0)
                        self.completion_tokens += usage_data.get("completion_tokens", 0)
                        logging.debug(
                            f"Updated tokens - Prompt: {self.prompt_tokens}, Completion: {self.completion_tokens}"
                        )
                        return

            if isinstance(response, dict):
                usage_data = response.get("usage")
            else:
                usage_data = getattr(response, "usage", None)

            if usage_data:
                with self._token_usage_lock:
                    self.prompt_tokens += usage_data.get("prompt_tokens", 0)
                    self.completion_tokens += usage_data.get("completion_tokens", 0)
                    logging.debug(
                        f"Updated tokens from response - Prompt: {self.prompt_tokens}, Completion: {self.completion_tokens}"
                    )

        except Exception as e:
            logging.error(f"Error in log_usage: {str(e)}")
            logging.error(f"Response type: {type(response)}")
            if isinstance(response, dict):
                logging.error(f"Response keys: {list(response.keys())}")

    def __call__(self, *args, **kwargs):
        """Override __call__ to ensure we capture usage from the history."""
        result = super().__call__(*args, **kwargs)

        if self.history and self.history[-1].get("usage"):
            usage_data = self.history[-1]["usage"]
            with self._token_usage_lock:
                self.prompt_tokens += usage_data.get("prompt_tokens", 0)
                self.completion_tokens += usage_data.get("completion_tokens", 0)

        return result

    def get_usage_and_reset(self):
        """Get the total tokens used and reset the token usage."""
        with self._token_usage_lock:
            usage = {
                self.model_name: {
                    "prompt_tokens": self.prompt_tokens,
                    "completion_tokens": self.completion_tokens,
                }
            }
            self.prompt_tokens = 0
            self.completion_tokens = 0
            return usage


class AzureOpenAIModel(dspy.LM):
    def __init__(
        self,
        api_base: Optional[str] = None,
        api_version: Optional[str] = None,
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        deployment_name: Optional[str] = None,
        model_type: Literal["chat", "text"] = "chat",
        **kwargs,
    ):
        model_identifier = (
            f"azure/{deployment_name}" if deployment_name else f"azure/{model}"
        )
        super().__init__(
            model=model_identifier,
            api_base=api_base,
            api_version=api_version,
            api_key=api_key,
            model_type=model_type,
            **kwargs,
        )
        self._token_usage_lock = threading.Lock()
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.model_name = deployment_name or model

    def log_usage(self, response):
        """Log the total tokens from the OpenAI API response."""
        try:
            if hasattr(self, "history") and self.history:
                last_call = self.history[-1]
                usage_data = last_call.get("usage")

                if usage_data:
                    with self._token_usage_lock:
                        self.prompt_tokens += usage_data.get("prompt_tokens", 0)
                        self.completion_tokens += usage_data.get("completion_tokens", 0)
                        logging.debug(
                            f"Updated tokens - Prompt: {self.prompt_tokens}, Completion: {self.completion_tokens}"
                        )
                        return

            if isinstance(response, dict):
                usage_data = response.get("usage")
            else:
                usage_data = getattr(response, "usage", None)

            if usage_data:
                with self._token_usage_lock:
                    self.prompt_tokens += usage_data.get("prompt_tokens", 0)
                    self.completion_tokens += usage_data.get("completion_tokens", 0)
                    logging.debug(
                        f"Updated tokens from response - Prompt: {self.prompt_tokens}, Completion: {self.completion_tokens}"
                    )

        except Exception as e:
            logging.error(f"Error in log_usage: {str(e)}")
            logging.error(f"Response type: {type(response)}")
            if isinstance(response, dict):
                logging.error(f"Response keys: {list(response.keys())}")

    def __call__(self, *args, **kwargs):
        """Override __call__ to ensure we capture usage from the history."""
        result = super().__call__(*args, **kwargs)

        if self.history and self.history[-1].get("usage"):
            usage_data = self.history[-1]["usage"]
            with self._token_usage_lock:
                self.prompt_tokens += usage_data.get("prompt_tokens", 0)
                self.completion_tokens += usage_data.get("completion_tokens", 0)

        return result

    def get_usage_and_reset(self):
        """Get the total tokens used and reset the token usage."""
        with self._token_usage_lock:
            usage = {
                self.model_name: {
                    "prompt_tokens": self.prompt_tokens,
                    "completion_tokens": self.completion_tokens,
                }
            }
            self.prompt_tokens = 0
            self.completion_tokens = 0
            return usage


class BedrockModel(dspy.LM):

    def __init__(
        self,
        model: str = "anthropic.claude-3-5-sonnet-20241022-v2:0",
        aws_region_name: Optional[str] = "us-west-2",
        aws_profile_name: Optional[str] = "USERNAME",
        model_type: Literal["chat", "text"] = "chat",
        **kwargs,
    ):
        MODEL_CONFIGS = {
            "llama-3-1-8B": {
                "model": "meta.llama3-1-8b-instruct-v1:0",
                "aws_region_name": "us-west-2",
            },
            "mistral-7b-v2": {
                "model": "mistral.mistral-7b-instruct-v0:2",
                "aws_region_name": "us-west-2",
            },
            "claude-3-5-sonnet": {
                "model": "anthropic.claude-3-5-sonnet-20241022-v2:0",
                "aws_region_name": "us-west-2",
            },
            "claude-3-7-sonnet": {
                "model": "anthropic.claude-3-7-sonnet-20250219-v1:0",
                "aws_region_name": "us-west-2",
            },
        }
        if model in MODEL_CONFIGS:
            config = MODEL_CONFIGS[model]
            model = config["model"]
            aws_region_name = config["aws_region_name"]

        model_identifier = f"bedrock/{model}"
        super().__init__(
            model=model_identifier,
            aws_region_name=aws_region_name,
            aws_profile_name=aws_profile_name,
            model_type=model_type,
            **kwargs,
        )
        self._token_usage_lock = threading.Lock()
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.model_name = model

    def log_usage(self, response):
        """Log the total tokens from the Bedrock API response."""
        try:
            if hasattr(self, "history") and self.history:
                last_call = self.history[-1]
                usage_data = last_call.get("usage")

                if usage_data:
                    with self._token_usage_lock:
                        self.prompt_tokens += usage_data.get("prompt_tokens", 0)
                        self.completion_tokens += usage_data.get("completion_tokens", 0)
                        logging.debug(
                            f"Updated tokens - Prompt: {self.prompt_tokens}, Completion: {self.completion_tokens}"
                        )
                        return

            if isinstance(response, dict):
                usage_data = response.get("usage")
            else:
                usage_data = getattr(response, "usage", None)

            if usage_data:
                with self._token_usage_lock:
                    self.prompt_tokens += usage_data.get("prompt_tokens", 0)
                    self.completion_tokens += usage_data.get("completion_tokens", 0)
                    logging.debug(
                        f"Updated tokens from response - Prompt: {self.prompt_tokens}, Completion: {self.completion_tokens}"
                    )

        except Exception as e:
            logging.error(f"Error in log_usage: {str(e)}")
            logging.error(f"Response type: {type(response)}")
            if isinstance(response, dict):
                logging.error(f"Response keys: {list(response.keys())}")

    def __call__(self, *args, **kwargs):
        """Override __call__ to ensure we capture usage from the history."""
        result = super().__call__(*args, **kwargs)

        if self.history and self.history[-1].get("usage"):
            usage_data = self.history[-1]["usage"]
            with self._token_usage_lock:
                self.prompt_tokens += usage_data.get("prompt_tokens", 0)
                self.completion_tokens += usage_data.get("completion_tokens", 0)

        return result

    def get_usage_and_reset(self):
        """Get the total tokens used and reset the token usage."""
        with self._token_usage_lock:
            usage = {
                self.model_name: {
                    "prompt_tokens": self.prompt_tokens,
                    "completion_tokens": self.completion_tokens,
                }
            }
            self.prompt_tokens = 0
            self.completion_tokens = 0
            return usage


class LMConfigs(ABC):
    """Abstract base class for language model configurations of the knowledge curation engine.

    The language model used for each part should be declared with a suffix '_lm' in the attribute name.
    """

    def __init__(self):
        pass

    def init_check(self):
        for attr_name in self.__dict__:
            if "_lm" in attr_name and getattr(self, attr_name) is None:
                logging.warning(
                    f"Language model for {attr_name} is not initialized. Please call set_{attr_name}()"
                )

    def collect_and_reset_lm_history(self):
        history = []
        for attr_name in self.__dict__:
            if "_lm" in attr_name and hasattr(getattr(self, attr_name), "history"):
                history.extend(getattr(self, attr_name).history)
                getattr(self, attr_name).history = []

        return history

    def collect_and_reset_lm_usage(self):
        combined_usage = []
        for attr_name in self.__dict__:
            if "_lm" in attr_name and hasattr(
                getattr(self, attr_name), "get_usage_and_reset"
            ):
                combined_usage.append(getattr(self, attr_name).get_usage_and_reset())

        model_name_to_usage = {}
        for usage in combined_usage:
            for model_name, tokens in usage.items():
                if model_name not in model_name_to_usage:
                    model_name_to_usage[model_name] = tokens
                else:
                    model_name_to_usage[model_name]["prompt_tokens"] += tokens[
                        "prompt_tokens"
                    ]
                    model_name_to_usage[model_name]["completion_tokens"] += tokens[
                        "completion_tokens"
                    ]

        return model_name_to_usage

    def log_v0(self):

        return OrderedDict(
            {
                attr_name: getattr(self, attr_name).kwargs
                for attr_name in self.__dict__
                if "_lm" in attr_name and hasattr(getattr(self, attr_name), "kwargs")
            }
        )

    def _sanitize_kwargs(self, kwargs):
        """Sanitize sensitive information from kwargs dictionary."""
        sanitized = copy.deepcopy(kwargs)
        sensitive_keys = ["api_key", "apiKey", "key", "secret", "password"]

        for key in sensitive_keys:
            if key in sanitized:
                sanitized[key] = "your-api-key"
        return sanitized

    def log(self):
        """Log configuration with sanitized sensitive information."""
        config_dict = OrderedDict()

        for attr_name in self.__dict__:
            if "_lm" in attr_name and hasattr(getattr(self, attr_name), "kwargs"):
                model = getattr(self, attr_name)
                settings = {
                    **model.kwargs,
                    "model": model.model,
                }
                settings = {k: v for k, v in settings.items() if v is not None}
                if "api_key" in settings:
                    settings["api_key"] = "your-api-key"
                config_dict[attr_name] = settings

        return config_dict

    def debug_print_config(self):
        """Debug method to safely print current configuration."""
        config = self.log()
        print("\nCurrent LM Configurations:")
        for model_name, settings in config.items():
            print(f"\n{model_name}:")
            for key, value in settings.items():
                print(f"  {key}: {value}")

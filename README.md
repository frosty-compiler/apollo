# apollo

This repository supports the research and development of *APOLLO: A Self-Guided Multi-Agent System for Scientific Article Generation inspired by Human Thinking*. It focuses on using multi-agent LLMs to generate structured, high-quality scientific articles.

## Installation Guide

### Prerequisites

Make sure to include the following environment variables in you shell configuration file (e.g., `~/.bashrc`, `~/.zshrc`.):

```sh
# API Credentials
export AZURE_API_KEY="TOKEN"
export AZURE_API_BASE="URL"
export AZURE_API_VERSION="DATE"  
export AZURE_DEPLOYMENT="gpt-4o-mini"

# HF authentication
export CACHE_DIR="your_cache_dir"
export HF_HOME="$CACHE_DIR/.cache/huggingface"
export HF_AUTH_TOKEN="TOKEN"

# Submodules Setup 
export PYTHONPATH="$HOME/apollo"
```


### Installing dependencies

#### Using Conda (Recommended)

Create and activate a new environment:

```sh
conda create -n myenv python=3.11
conda activate myenv
conda install -c conda-forge gcc=12.3 gxx=12.3
pip install --extra-index-url https://download.pytorch.org/whl/cu121 torch
pip install -r requirements.txt
```
#### Hugging Face Login

To access pre-trained LLMs, log in using the Hugging Face CLI:

```sh
huggingface-cli login
```


## Dataset

The dataset used for the evaluation of our method uses the `SciWiki-2k`, a collection of 2k high-quality Wikipedia articles. To download the dataset, run the following command:

```bash
bash ./scripts/download_data.sh
```

## Models
This repository leverages multiple state-of-the-art LLMs to generate and refine topic pages. Each model serves a specific role in the multi-agent pipeline. Here a list of the models used:

| Name                           | Role                        |
|--------------------------------|-----------------------------|
| OpenAI's GPT-4o-mini           | Article generation          |
| Snowflake-arctic-embed-m-v2.0  | Tokenizer for retrieval     |
| Claude-3-5-Sonnet              | Fact checking               |
| Prometheus-7b-v2.0             | Rubric scoring              |


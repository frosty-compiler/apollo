# =============================================
# Helper Functions for General Management
# =============================================

def get_device(verbose=False):
    import torch

    if torch.cuda.is_available():
        device = torch.device("cuda")
    elif torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")

    if verbose:
        print(f"Using device: {device}")
    return device



# =============================================
# Mapping for Domain Abbreviations
# =============================================

domain_mapping = {
    "Agricultural & Biological Sciences": "AgriBio",
    "Biochemistry, Genetics & Molecular Biology": "Biochem_Genetics_MolBio",
    "Chemical Engineering": "ChemicalEngineering",
    "Chemistry": "Chemistry",
    "Computer Science": "ComputerScience",
    "Economics": "Economics",
    "Earth & Planetary Sciences": "EarthPlanetaryScience",
    "Engineering": "Engineering",
    "Food Science": "FoodScience",
    "Immunology & Microbiology": "Immunology_Microbiology",
    "Mathematics": "Mathematics",
    "Medicine & Dentistry": "Med_Dentistry",
    "Neuroscience": "Neuro",
    "Nursing & Health Professions": "Nursing_HealthProf",
    "Pharmacology, Toxicology & Pharmaceutical Science": "Pharma_Tox",
    "Physics & Astronomy": "Physics",
    "Psychology": "Psychology",
    "Social Sciences": "SocialSciences",
    "Materials Science": "MaterialScience",
    "Veterinary Science & Veterinary Medicine": "VeterinaryMedicine",
}

import os
from typing import Optional
from .file_handler import load_json

def load_domains(
    selected_domains: Optional[str] = None,
    dataset: str = "SciWiki-100",
) -> dict:
    from config.paths import data_dir

    file_path = os.path.join(data_dir, dataset, "topics", "topics_per_domain.json")
    all_domains = load_json(file_path)

    if not selected_domains:
        return all_domains

    domain_list = [d.strip() for d in selected_domains.split(",")]
    filtered_domains = {d: all_domains[d] for d in domain_list if d in all_domains}

    if not filtered_domains:
        print(f"No valid domains found. Available: {list(all_domains.keys())}")
        return None

    return filtered_domains
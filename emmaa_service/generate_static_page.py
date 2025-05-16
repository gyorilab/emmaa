import json
from pathlib import Path
from typing import Dict

from tqdm import tqdm

from emmaa.util import find_latest_s3_file, load_json_from_s3, does_exist


HERE = Path(__file__).parent.resolve()
JSON_PATH = HERE / "models.json"

MODELS = [
    "aml",
    "brca",
    "covid19",
    "covid19_dev",
    "covid19_inflammasome",
    "covid19_map",
    "food_insecurity",
    "luad",
    "marm_model",
    "monkeypox",
    "ms",
    "nf",
    "paad",
    "painmachine",
    "pompe",
    "prad",
    "rasmachine",
    "rasmodel",
    "skcm",
    "vitiligo",
]


def get_meta_data(model: str) -> Dict[str, str]:
    """Get the metadata for a model."""
    # Todo: handle models that have multiple test corpora
    bucket = "emmaa"
    prefix_meta_json = f"models/{model}/{model}_model_meta.json"
    prefix_config = f"models/{model}/config.json"

    if does_exist(bucket=bucket, prefix=prefix_meta_json):
        meta_json = load_json_from_s3(bucket=bucket, key=prefix_meta_json)
    else:
        meta_json = {}

    config_json = load_json_from_s3(bucket=bucket, key=prefix_config)

    latest_model_pkl = find_latest_s3_file(
        bucket=bucket,
        prefix=f"models/{model}/model",
        extension="pkl"
    )
    latest_model_test = find_latest_s3_file(
        bucket=bucket,
        prefix=f"stats/{model}/test",
    )

    def _get_val(key: str, default: str) -> str:
        """Get the value from the metadata or return the default."""
        if key in meta_json:
            return meta_json[key]
        if key in config_json:
            return config_json[key]
        return default

    model_short_name = _get_val("name", "")
    if not model_short_name:
        model_short_name = model

    human_readable_name = _get_val("human_readable_name", "")
    if not human_readable_name:
        human_readable_name = model_short_name

    return {
        "model": model,
        "model_short_name": model_short_name,
        "name": human_readable_name,
        "description": config_json["description"],
        "model_path": latest_model_pkl or "",
        "test_path": latest_model_test or "",
        "ndex": config_json.get("ndex", {}).get("network", "")  # in config.json -> ndex -> network
    }


def get_model_metadata() -> Dict[str, Dict[str, str]]:
    """Get the metadata for all models."""
    model_metadata = {}
    for model in tqdm(MODELS, desc="Loading model metadata", unit="model"):
        model_metadata[model] = get_meta_data(model)
    return model_metadata


if __name__ == "__main__":
    # Get the metadata for all models
    model_metadata = get_model_metadata()

    # Save the metadata to a JSON file
    with open(JSON_PATH, "w") as f:
        json.dump(model_metadata, f, indent=2)

    # Render page

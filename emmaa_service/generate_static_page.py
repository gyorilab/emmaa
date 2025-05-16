import json
from pathlib import Path
from typing import Dict

from tqdm import tqdm

from emmaa.util import find_latest_s3_file, load_json_from_s3, does_exist


HERE = Path(__file__).parent.resolve()
JSON_PATH = HERE / "models.json"
TEMPLATES_DIRECTORY = HERE / "templates"
HTML_PATH = TEMPLATES_DIRECTORY / "static_page.html"

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


def get_jinja_env():
    """Get the Jinja2 environment."""
    from jinja2 import Environment, FileSystemLoader

    env = Environment(
        autoescape=True,
        loader=FileSystemLoader(TEMPLATES_DIRECTORY),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    return env


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
    import argparse
    parser = argparse.ArgumentParser(
        description="Generate a static page for the models."
    )
    parser.add_argument(
        "--regenerate-json",
        action="store_true",
        help="Regenerate the JSON file with model metadata.",
    )
    args = parser.parse_args()
    if args.regenerate_json or not JSON_PATH.exists():
        # Get the metadata for all models and save it to a JSON file
        model_metadata = get_model_metadata()
        with open(JSON_PATH, "w") as f:
            json.dump(model_metadata, f, indent=2)
    else:
        # Load the metadata from the JSON file
        model_metadata = json.loads(JSON_PATH.read_text())

    # Render page
    environment = get_jinja_env()
    template = environment.get_template("static_page_template.html")
    html = template.render(
        model_metadata=model_metadata,
        models=MODELS,
    )

    # Save the rendered HTML to a file
    print(f"Saving HTML to {HTML_PATH}")
    HTML_PATH.write_text(html)

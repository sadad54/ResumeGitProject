"""ML / model infrastructure detection (checklist §1.5), deterministic layer."""

from proofhire_worker.ingestion.tech_extraction import extract


def test_requirements_txt_with_training_and_tracking_deps():
    meta = extract("requirements.txt", "torch==2.3\ntransformers>=4.40\nmlflow\nfaiss-cpu\nrequests\n")
    assert meta["ml_infrastructure"] == ["deep_learning", "experiment_tracking", "llm_nlp", "vector_search"]


def test_pyproject_classical_ml():
    meta = extract("pyproject.toml", 'dependencies = [\n  "scikit-learn>=1.4",\n  "xgboost>=2",\n  "fastapi>=0.115",\n]\n')
    assert meta["ml_infrastructure"] == ["classical_ml"]


def test_package_json_llm_orchestration():
    meta = extract("package.json", '{"dependencies": {"langchain": "^0.2", "openai": "^4", "next": "16"}}')
    assert meta["ml_infrastructure"] == ["llm_api", "llm_orchestration"]


def test_no_ml_deps_yields_no_ml_key():
    meta = extract("requirements.txt", "fastapi\nsqlalchemy\nhttpx\n")
    assert "ml_infrastructure" not in meta


def test_gpu_base_image_is_an_ml_signal():
    meta = extract("Dockerfile", "FROM nvcr.io/nvidia/pytorch:24.05-py3\nRUN pip install -r requirements.txt\n")
    assert meta["ml_infrastructure"] == ["gpu_container"]
    assert extract("Dockerfile", "FROM python:3.13-slim\n").get("ml_infrastructure") is None


def test_model_artifacts_and_pipeline_files_detected_by_path_alone():
    assert extract("models/encoder.safetensors", "")["ml_infrastructure"] == ["ml_project_layout", "model_artifact"]
    assert extract("dvc.yaml", "stages: {}")["ml_infrastructure"] == ["data_versioning"]
    assert extract("serving/config.pbtxt", "")["ml_infrastructure"] == ["model_serving"]
    assert extract("checkpoints/epoch_3.ckpt", "")["ml_infrastructure"] == ["ml_project_layout", "model_artifact"]


def test_ordinary_source_file_is_not_flagged():
    assert extract("app/main.py", "print('hi')") == {}

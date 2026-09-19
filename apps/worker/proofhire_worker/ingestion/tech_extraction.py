"""Deterministic technology extraction (PRD §15 Stage 3) — runs BEFORE any LLM call,
on P0 artifacts (manifests, CI configs, Dockerfiles). Cheap, exact-match signal that
also feeds Evidence confidence scoring in Phase 2 (deterministic + semantic fusion).
"""

import json
import re

_FRAMEWORK_HINTS: dict[str, list[str]] = {
    "fastapi": ["python"],
    "django": ["python"],
    "flask": ["python"],
    "next": ["typescript", "javascript"],
    "react": ["typescript", "javascript"],
    "express": ["typescript", "javascript"],
    "dramatiq": ["python"],
    "celery": ["python"],
    "sqlalchemy": ["python"],
    "pytorch": ["python"],
    "torch": ["python"],
    "tensorflow": ["python"],
    "scikit-learn": ["python"],
    "pandas": ["python"],
}


# ML / model infrastructure (checklist §1.5). Two signals, both deterministic:
# dependency names that only appear in ML codebases, and files whose existence
# means a model was trained, tracked, or served. Either alone can be a false
# positive (a data-analysis notebook imports pandas); the extractor reports
# what it saw and lets confidence scoring weigh it, rather than deciding
# "this is an ML repo" here.
ML_DEPENDENCY_SIGNALS: dict[str, str] = {
    # training / modelling
    "torch": "deep_learning", "pytorch": "deep_learning", "tensorflow": "deep_learning",
    "keras": "deep_learning", "jax": "deep_learning", "flax": "deep_learning",
    "pytorch-lightning": "deep_learning", "lightning": "deep_learning",
    "transformers": "llm_nlp", "sentence-transformers": "llm_nlp", "peft": "llm_nlp",
    "trl": "llm_nlp", "vllm": "llm_serving", "openai": "llm_api", "anthropic": "llm_api",
    "langchain": "llm_orchestration", "llama-index": "llm_orchestration", "llama_index": "llm_orchestration",
    "scikit-learn": "classical_ml", "sklearn": "classical_ml", "xgboost": "classical_ml",
    "lightgbm": "classical_ml", "catboost": "classical_ml", "statsmodels": "classical_ml",
    # experiment tracking / registry / pipelines
    "mlflow": "experiment_tracking", "wandb": "experiment_tracking", "neptune": "experiment_tracking",
    "dvc": "data_versioning", "kubeflow": "ml_pipelines", "kfp": "ml_pipelines",
    "bentoml": "model_serving", "torchserve": "model_serving", "onnxruntime": "model_serving",
    "triton": "model_serving", "ray": "distributed_training", "deepspeed": "distributed_training",
    # vector / retrieval
    "faiss": "vector_search", "faiss-cpu": "vector_search", "faiss-gpu": "vector_search",
    "pgvector": "vector_search", "chromadb": "vector_search", "pinecone-client": "vector_search",
    "qdrant-client": "vector_search", "weaviate-client": "vector_search",
    # evaluation
    "evaluate": "ml_evaluation", "ragas": "ml_evaluation", "deepeval": "ml_evaluation",
}

ML_FILE_SIGNALS: dict[str, str] = {
    "dvc.yaml": "data_versioning", "dvc.lock": "data_versioning", ".dvc": "data_versioning",
    "mlflow.yaml": "experiment_tracking", "MLproject": "experiment_tracking",
    "wandb": "experiment_tracking", "params.yaml": "ml_pipelines",
    "model_card.md": "model_card", "MODEL_CARD.md": "model_card",
    "bentofile.yaml": "model_serving", "config.pbtxt": "model_serving",
}
ML_MODEL_EXTENSIONS = {".pt", ".pth", ".ckpt", ".safetensors", ".onnx", ".h5", ".keras",
                       ".pkl", ".joblib", ".tflite", ".pb", ".gguf"}


def _ml_signals_from_deps(deps: list[str]) -> dict:
    found = sorted({ML_DEPENDENCY_SIGNALS[d.lower()] for d in deps if d.lower() in ML_DEPENDENCY_SIGNALS})
    return {"ml_infrastructure": found} if found else {}


def extract_ml_from_path(path: str) -> dict:
    """Signals from a file's *name*, for artifacts whose content we never read
    (model weights are binary and excluded from fetch)."""
    name = path.rsplit("/", 1)[-1]
    lower = path.lower()
    signals: set[str] = set()
    for filename, signal in ML_FILE_SIGNALS.items():
        if name == filename or f"/{filename}/" in f"/{lower}/" or lower.endswith(f"/{filename.lower()}"):
            signals.add(signal)
    if any(name.lower().endswith(ext) for ext in ML_MODEL_EXTENSIONS):
        signals.add("model_artifact")
    if any(seg in f"/{lower}" for seg in ("/models/", "/checkpoints/", "/weights/", "/notebooks/", "/experiments/")):
        signals.add("ml_project_layout")
    return {"ml_infrastructure": sorted(signals)} if signals else {}


def extract_from_package_json(content: str) -> dict:
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return {}
    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
    return {
        "language": "javascript/typescript",
        "dependencies": sorted(deps.keys()),
        "frameworks": sorted(name for name in _FRAMEWORK_HINTS if name in deps),
        **_ml_signals_from_deps(list(deps)),
    }


def extract_from_pyproject_toml(content: str) -> dict:
    # Lightweight regex extraction rather than a full TOML parse, to avoid adding a
    # tomllib version dependency edge case; good enough for dependency name signal.
    deps = re.findall(r'^\s*"?([a-zA-Z0-9_\-]+)(?:\[[^\]]*\])?\s*[><=~^]', content, re.MULTILINE)
    return {
        "language": "python",
        "dependencies": sorted(set(deps)),
        "frameworks": sorted(name for name in _FRAMEWORK_HINTS if name in {d.lower() for d in deps}),
        **_ml_signals_from_deps(deps),
    }


def extract_from_requirements_txt(content: str) -> dict:
    deps = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name = re.split(r"[><=~\[;]", line, maxsplit=1)[0].strip()
        if name:
            deps.append(name.lower())
    return {
        "language": "python",
        "dependencies": sorted(set(deps)),
        "frameworks": sorted(name for name in _FRAMEWORK_HINTS if name in deps),
        **_ml_signals_from_deps(deps),
    }


def extract_from_dockerfile(content: str) -> dict:
    base_images = re.findall(r"^FROM\s+(\S+)", content, re.MULTILINE | re.IGNORECASE)
    out: dict = {"container": True, "base_images": base_images}
    # A CUDA/PyTorch/TensorFlow base image is as strong an ML-infra signal as
    # a dependency name, and it's the one that says "trains or serves on GPU".
    gpu = [b for b in base_images if re.search(r"cuda|nvidia|pytorch|tensorflow|nvcr\.io", b, re.IGNORECASE)]
    if gpu:
        out["ml_infrastructure"] = ["gpu_container"]
    return out


def extract_from_ci_config(path: str, content: str) -> dict:
    if ".github/workflows/" in path:
        provider = "github_actions"
    elif ".gitlab-ci" in path:
        provider = "gitlab_ci"
    elif "circleci" in path:
        provider = "circleci"
    else:
        provider = "unknown"
    return {"ci_provider": provider}


def extract(path: str, content: str) -> dict:
    """Dispatches to the right deterministic extractor based on filename."""
    name = path.rsplit("/", 1)[-1]
    if name == "package.json":
        return extract_from_package_json(content)
    if name == "pyproject.toml":
        return extract_from_pyproject_toml(content)
    if name == "requirements.txt":
        return extract_from_requirements_txt(content)
    if name in {"Dockerfile"} or name.startswith("Dockerfile."):
        return extract_from_dockerfile(content)
    if ".github/workflows/" in path or name in {".gitlab-ci.yml"}:
        return extract_from_ci_config(path, content)
    return extract_ml_from_path(path)

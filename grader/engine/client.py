"""Anthropic client setup and environment loading."""

import os
from pathlib import Path

import anthropic


DEFAULT_MODELS = {
    "bedrock": "us.anthropic.claude-sonnet-4-6",
    "anthropic": "claude-sonnet-4-6",
}


def load_env(env_path: Path) -> None:
    """Load key=value pairs from a .env file into os.environ (no overwrite)."""
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip())


def create_client() -> anthropic.Anthropic | anthropic.AnthropicBedrock:
    """Create the appropriate Anthropic client (direct API or Bedrock)."""
    provider = os.environ.get("ANTHROPIC_PROVIDER", "bedrock").strip().lower()
    if provider == "bedrock":
        region = os.environ.get(
            "AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        ).strip()
        return anthropic.AnthropicBedrock(aws_region=region)
    else:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set.")
        return anthropic.Anthropic(api_key=api_key)


def get_model() -> str:
    """Get the model ID from env or use the default for the configured provider."""
    explicit = os.environ.get("ANTHROPIC_MODEL", "").strip()
    if explicit:
        return explicit
    provider = os.environ.get("ANTHROPIC_PROVIDER", "bedrock").strip().lower()
    return DEFAULT_MODELS.get(provider, DEFAULT_MODELS["bedrock"])


def init_env(root: Path) -> None:
    """Load .env files from the project root and grader directory."""
    load_env(root / ".env")
    load_env(root / "grader" / ".env")

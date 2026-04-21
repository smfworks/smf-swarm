"""SMF Swarm — Configuration Wizard and persistent settings.

Handles:
  - Interactive first-run configuration (terminal wizard)
  - Loading / saving config to ~/.config/smf-swarm/config.yaml
  - LLM client factory with any provider
  - Environment variable fallbacks (O_API_KEY, OPENAI_BASE_URL, MODEL_NAME)
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Literal, Optional

try:
    import yaml
except ImportError:
    yaml = None  # JSON fallback

from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "smf-swarm"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.yaml"
ENV_CONFIG_FILE = DEFAULT_CONFIG_DIR / ".env"

# ─── Data model ─────────────────────────────────

@dataclass
class LLMConfig:
    provider: str = "ollama"          # ollama | openai | anthropic | custom
    model: str = "kimi-k2.6:cloud"   # any model name the provider supports
    base_url: str = "http://localhost:11434/v1"
    api_key: str = "ollama"
    temperature: float = 0.3
    timeout: int = 180
    max_retries: int = 1
    extra_headers: dict = field(default_factory=dict)

    def to_kwargs(self) -> dict:
        """Return kwargs for ChatOpenAI constructor."""
        return {
            "model": self.model,
            "base_url": self.base_url,
            "api_key": self.api_key,
            "temperature": self.temperature,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
        }


@dataclass
class SwarmConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    default_mode: str = "standard"               # standard | debate | full
    default_domain: str = "general"
    social_agents: int = 15
    social_rounds: int = 4
    debaters: int = 3
    debate_rounds: int = 2
    output_dir: str = str(Path.home() / "smf-swarm" / "output")
    memory_dir: str = str(Path.home() / "smf-swarm" / "memory")
    verbose: bool = True


# ─── Environment fallback ─────────────────────────

def _env_override(cfg: SwarmConfig) -> SwarmConfig:
    """Override config from environment variables if set."""
    if os.getenv("MODEL_NAME"):
        cfg.llm.model = os.getenv("MODEL_NAME")
    if os.getenv("OPENAI_BASE_URL"):
        cfg.llm.base_url = os.getenv("OPENAI_BASE_URL")
    if os.getenv("O_API_KEY"):
        cfg.llm.api_key = os.getenv("O_API_KEY")
    return cfg


# ─── Load / save ──────────────────────────────────

def load_config(path: Path | None = None) -> SwarmConfig:
    """Load config from file, or return defaults with env overrides."""
    cfg = SwarmConfig()
    if path is None:
        path = DEFAULT_CONFIG_FILE

    if path.exists():
        text = path.read_text()
        if yaml:
            data = yaml.safe_load(text) or {}
        else:
            data = json.loads(text)
        if data.get("llm"):
            cfg.llm = LLMConfig(**data["llm"])
        for key in ("default_mode", "default_domain", "social_agents", "social_rounds",
                    "debaters", "debate_rounds", "output_dir", "memory_dir", "verbose"):
            if key in data:
                setattr(cfg, key, data[key])

    # Env overrides (highest priority — ephemeral)
    cfg = _env_override(cfg)
    return cfg


def save_config(cfg: SwarmConfig, path: Path | None = None):
    """Save config to disk."""
    if path is None:
        path = DEFAULT_CONFIG_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(cfg)
    if yaml:
        path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
    else:
        json_path = path.with_suffix(".json")
        json_path.write_text(json.dumps(data, indent=2))


# ─── LLM factory ──────────────────────────────────

def create_llm(cfg: LLMConfig | None = None) -> BaseChatModel:
    """Create a LangChain LLM client from config."""
    if cfg is None:
        cfg = load_config().llm

    if cfg.provider in ("openai", "ollama", "custom"):
        return ChatOpenAI(**cfg.to_kwargs())
    else:
        raise ValueError(
            f"Provider '{cfg.provider}' is not directly supported. "
            f"Use 'openai' with a custom base_url, or add an adapter in llm_adapters.py."
        )


# ─── Interactive wizard ───────────────────────────

def configure() -> SwarmConfig:
    """Interactive terminal wizard for first-time setup."""
    print("\n╔════════════════════════════════════════════════════════════╗")
    print("║       SMF Swarm — First-Time Configuration Wizard          ║")
    print("╚════════════════════════════════════════════════════════════╝\n")

    cfg = SwarmConfig()

    # ── Step 1: provider
    print("Step 1/5 — Choose your LLM provider")
    print("  [1] Ollama (local models) — RECOMMENDED for beginners")
    print("  [2] OpenAI (GPT-4, GPT-3.5, etc.)")
    print("  [3] Anthropic (Claude)")
    print("  [4] Custom / other (e.g., Groq, Anyscale, Together)")
    prov = input("\nEnter 1–4 [default: 1]: ").strip() or "1"
    choices = {"1": "ollama", "2": "openai", "3": "anthropic", "4": "custom"}
    cfg.llm.provider = choices.get(prov, "ollama")

    # ── Step 2: model name
    defaults = {
        "ollama": "kimi-k2.6:cloud",
        "openai": "gpt-4o",
        "anthropic": "claude-3-opus-20240229",
        "custom": "model-name",
    }
    model_default = defaults[cfg.llm.provider]
    if cfg.llm.provider == "ollama":
        print(f"\nStep 2/5 — Model name")
        print("  Popular options: llama3.3, qwen2.5, kimi-k2.6:cloud, mistral")
    else:
        print(f"\nStep 2/5 — Model name")
    model = input(f"Model [default: {model_default}]: ").strip() or model_default
    cfg.llm.model = model

    # ── Step 3: base URL
    url_defaults = {
        "ollama": "http://localhost:11434/v1",
        "openai": "https://api.openai.com/v1",
        "anthropic": "https://api.anthropic.com/v1",
        "custom": "https://your-provider.com/v1",
    }
    url_default = url_defaults[cfg.llm.provider]
    if cfg.llm.provider == "ollama":
        print(f"\nStep 3/5 — Ollama server URL")
        print("  If Ollama runs locally, leave default. If on another machine, enter its IP.")
    else:
        print(f"\nStep 3/5 — API base URL")
    url = input(f"Base URL [default: {url_default}]: ").strip() or url_default
    cfg.llm.base_url = url

    # ── Step 4: API key
    print(f"\nStep 4/5 — API key")
    if cfg.llm.provider == "ollama":
        print("  For Ollama, any non-empty string works (e.g., 'ollama').")
    key = input(f"API key [default: ollama]: ").strip() or "ollama"
    cfg.llm.api_key = key

    # ── Step 5: defaults
    print(f"\nStep 5/5 — Default prediction mode")
    print("  [1] Standard  — fastest, single-model prediction")
    print("  [2] Debate    — adversarial ensemble (recommended)")
    print("  [3] Full      — standard + debate + social validation (most thorough)")
    mode = input("Default mode [default: 2]: ").strip() or "2"
    cfg.default_mode = {k: v for k, v in [("1", "standard"), ("2", "debate"), ("3", "full")]}.get(mode, "debate")

    # ── Save
    print(f"\n→ Saving configuration to {DEFAULT_CONFIG_FILE}")
    save_config(cfg)
    print("✅ Configuration saved successfully!\n")
    print(f"Model: {cfg.llm.model} via {cfg.llm.provider}")
    print(f"Base URL: {cfg.llm.base_url}")
    print(f"Default mode: {cfg.default_mode}")
    print(f"\nRun  smf-swarm predict \"your question here\"  to make your first prediction.")

    return cfg


# ─── Singleton accessor ───────────────────────────

_cfg: Optional[SwarmConfig] = None

def get_config(force_reload: bool = False) -> SwarmConfig:
    global _cfg
    if _cfg is None or force_reload:
        _cfg = load_config()
    return _cfg

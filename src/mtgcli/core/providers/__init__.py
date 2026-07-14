"""core.providers — AI-agent CLI providers for headless deck builds (v0.9.0).

The GUI ships the KNOWLEDGE (mtg tool + agent instruction files); the user brings
the INTELLIGENCE — any agent CLI. Providers detect what's installed and run the
build headlessly inside a sandboxed workspace. v0.9.0 implements ClaudeCodeProvider
(build-capable) and OllamaProvider (detection-only).
"""
from mtgcli.core.providers.antigravity import AntigravityProvider
from mtgcli.core.providers.base import (
    AgentProvider,
    ProviderBuildUnsupported,
    ProviderInfo,
    ProviderResult,
)
from mtgcli.core.providers.claude_code import ClaudeCodeProvider
from mtgcli.core.providers.codex import CodexProvider
from mtgcli.core.providers.manager import ProviderManager
from mtgcli.core.providers.ollama import OllamaProvider

__all__ = [
    "AgentProvider", "ProviderBuildUnsupported", "ProviderInfo", "ProviderResult",
    "AntigravityProvider", "ClaudeCodeProvider", "CodexProvider", "OllamaProvider",
    "ProviderManager",
]

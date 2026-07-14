"""ProviderManager — the registry the GUI (and a future `mtg providers` command) use."""
from typing import Dict, List, Optional

from mtgcli.core.providers.antigravity import AntigravityProvider
from mtgcli.core.providers.base import AgentProvider, ProviderInfo
from mtgcli.core.providers.claude_code import ClaudeCodeProvider
from mtgcli.core.providers.codex import CodexProvider
from mtgcli.core.providers.ollama import OllamaProvider

# TODO (post-v0.9.0): GeminiProvider (`gemini -p`) — the AgentProvider interface
# is already vendor-neutral; add + register here.
# Registration order matters: default_build_provider() prefers the FIRST installed
# build-capable provider — claude-code stays the default.


class ProviderManager:
    def __init__(self, providers: Optional[List[AgentProvider]] = None):
        self._providers: Dict[str, AgentProvider] = {
            p.name: p for p in (providers if providers is not None
                                else [ClaudeCodeProvider(), AntigravityProvider(),
                                      CodexProvider(), OllamaProvider()])
        }

    def get(self, name: str) -> Optional[AgentProvider]:
        return self._providers.get(name)

    def detect_all(self) -> List[ProviderInfo]:
        return [p.detect() for p in self._providers.values()]

    def default_build_provider(self) -> Optional[str]:
        """First INSTALLED provider that can build (claude-code preferred by
        registration order)."""
        for p in self._providers.values():
            if p.supports_build and p.detect().installed:
                return p.name
        return None

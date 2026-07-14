"""core — reusable business-logic services shared by the CLI and the GUI API.

The service contract (REFACTOR_MAP.md):

1. Services are stateless modules with plain functions. Dependencies (repo, paths)
   are PARAMETERS with config defaults — the CLI passes its own module globals
   through so per-module test monkeypatching keeps working.
2. Services return data; callers do I/O (printing, JSON emission, file writes) —
   unless the filesystem IS the service (e.g. build-workspace creation).
3. Classes only where there is real state (ProviderManager, JobRegistry).
"""

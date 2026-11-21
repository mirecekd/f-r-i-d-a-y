# backend/app/memory/__init__.py
"""Awareness over agentmemory: today's digest, recall, memory graph and the session-start briefing.

Everything here is best effort: when agentmemory is unreachable the public functions return
`{"error": ...}` (or an empty briefing) and never raise.
"""

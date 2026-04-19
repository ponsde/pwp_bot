"""Result quality audit module.

Exposes pure check functions used by scripts/audit_results.py. Every public
entrypoint takes plain dicts / paths so the check layer stays independent of
openpyxl, sqlite3, or the LLM client.
"""

"""MCP server — Model Context Protocol server (§9.4, §13, §19.20, §19.21).

A standalone process that exposes MCP tools for merchant analytics.
Imports shared facades from `backend/api/` — identical business logic to REST.

Auth: mTLS or signed API keys (§9.4) — not JWT.
AuthZ: merchant_ref → UUID resolved once per request, every downstream
call carries object-level AuthZ identical to REST.
"""

"""MCP server entry point (§9.4, §13).

Uses the `mcp` library's Server class with stdio transport.
Auth: signed API keys or mTLS (§9.4), NOT JWT.

The MCP protocol passes auth via request headers/metadata. The server
extracts the principal, resolves merchant_ref, enforces AuthZ, and calls
the SAME facades the REST controllers use.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "api")
)

import django

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE", "config.settings.dev"
)
os.environ.setdefault("DJANGO_SECRET_KEY", "mcp-server-secret-key")
os.environ.setdefault("JWT_ACCESS_SECRET", "test-access-secret")
os.environ.setdefault("JWT_REFRESH_SECRET", "test-refresh-secret")

try:
    django.setup()
except Exception:
    pass

from mcp.server import Server
from mcp.types import (
    CallToolRequest,
    CallToolResult,
    ListToolsRequest,
    ListToolsResult,
    PaginatedRequestParams,
    TextContent,
    Tool,
)

from api.mcp_registry import API_KEY_SECRET
from auth.mcp_auth import McpAuthService, McpPrincipal
from tools.mcp_tools import (
    ASK_AGENT,
    LIST_INSIGHTS,
    TRIGGER_AGENTIC_SUMMARY,
    handle_ask_agent,
    handle_list_insights,
    handle_trigger_agentic_summary,
)


def _extract_principal(request_headers: dict | None) -> McpPrincipal | None:
    """Extract authenticated principal from MCP request headers (§9.4)."""
    if not request_headers:
        return None

    auth_header = request_headers.get("authorization", "")
    api_key: str | None = None

    if auth_header.startswith("ApiKey "):
        api_key = auth_header[7:]
    elif auth_header.startswith("Bearer "):
        api_key = auth_header[7:]
    elif auth_header:
        api_key = auth_header

    client_cert_dn = request_headers.get("x-mtls-dn")

    auth_service = McpAuthService(api_key_secret=API_KEY_SECRET)
    principal = auth_service.authenticate(api_key=api_key)
    if principal:
        return principal

    if client_cert_dn:
        return auth_service.authenticate(
            client_cert={"subject": client_cert_dn}
        )

    return None


_TOOLS: dict[str, tuple[Tool, object]] = {
    "trigger_agentic_summary": (
        TRIGGER_AGENTIC_SUMMARY,
        handle_trigger_agentic_summary,
    ),
    "list_insights": (
        LIST_INSIGHTS,
        handle_list_insights,
    ),
    "ask_agent": (
        ASK_AGENT,
        handle_ask_agent,
    ),
}


app = Server("zarinpal-mcp")


async def _handle_list_tools(
    request: PaginatedRequestParams,
    context,
) -> ListToolsResult:
    """List available MCP tools (§9.4)."""
    tools = [tool for tool, _ in _TOOLS.values()]
    return ListToolsResult(tools=tools)


async def _handle_call_tool(
    request,
    context,
) -> CallToolResult:
    """Call a tool with auth + merchant resolution (§9.4, §13).

    Every tool call:
    1. Authenticates via API key or mTLS
    2. Resolves merchant_ref → UUID once (merchant-scoped by construction)
    3. Enforces object-level AuthZ via AuthzEnforcer
    4. Calls the same facade logic as REST
    """
    request_headers = getattr(context, "request_headers", {}) or {}
    principal = _extract_principal(request_headers)

    if principal is None:
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=json.dumps(
                    {
                        "error": "AUTHENTICATION_REQUIRED",
                        "code": "authentication_required",
                    }
                ),
            )],
        )

    tool_name = request.name
    arguments = request.arguments or {}

    if tool_name not in _TOOLS:
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=json.dumps(
                    {"error": "UNKNOWN_TOOL", "tool": tool_name}
                ),
            )],
        )

    _, handler = _TOOLS[tool_name]

    try:
        result = handler(arguments, principal)
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=json.dumps(result, default=str),
            )],
        )
    except Exception as exc:
        error_name = type(exc).__name__
        if "PermissionDenied" in error_name or "PermissionError" in error_name:
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "error": "NOT_ENTITLED_TO_MERCHANT",
                            "code": "forbidden",
                        }
                    ),
                )],
            )
        if "MERCHANT_NOT_FOUND" in str(exc):
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "error": "MERCHANT_NOT_FOUND",
                            "code": "merchant_not_found",
                        }
                    ),
                )],
            )
        raise


app.add_request_handler(
    "tools/list", ListToolsRequest, _handle_list_tools
)
app.add_request_handler(
    "tools/call", CallToolRequest, _handle_call_tool
)


def run_server() -> None:
    """Run the MCP server via stdio."""
    from mcp.server import stdio
    from mcp.server.lowlevel import server as ls

    async def _run():
        read_stream, write_stream = await stdio.stdio_server()
        await ls.serve_dual_era_loop(
            app,
            read_stream,
            write_stream,
            lifespan_state=None,
        )

    asyncio.run(_run())


if __name__ == "__main__":
    run_server()

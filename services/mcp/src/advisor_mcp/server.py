"""MCP server. Tenant-scoped tools arrive in PLAN 6.2 (SPEC §12)."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

server = MCPServer(
    name="plant-advisor",
    instructions="Read-only, tenant-scoped tools for the Plant Advisor ticket copilot.",
    version="0.1.0",
)

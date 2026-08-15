from __future__ import annotations

import json
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPFinanceClient:
    def __init__(self, session: ClientSession):
        self.session = session

    async def openai_tools(self) -> list[dict[str, Any]]:
        response = await self.session.list_tools()
        return [
            {
                "type": "function",
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.inputSchema,
            }
            for tool in response.tools
        ]

    async def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result = await self.session.call_tool(name, arguments)
        if result.isError:
            message = " ".join(getattr(item, "text", "") for item in result.content)
            raise RuntimeError(message or f"MCP tool {name} failed")
        structured = getattr(result, "structuredContent", None)
        if structured:
            return structured.get("result", structured)
        text = "".join(getattr(item, "text", "") for item in result.content)
        return json.loads(text) if text else {}


@asynccontextmanager
async def finance_mcp_client() -> AsyncIterator[MCPFinanceClient]:
    src_dir = str(Path(__file__).resolve().parents[1])
    env = os.environ.copy()
    env["PYTHONPATH"] = src_dir + os.pathsep + env.get("PYTHONPATH", "")
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "finresearch.mcp_server"],
        env=env,
    )
    async with stdio_client(params) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            yield MCPFinanceClient(session)

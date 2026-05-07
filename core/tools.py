from typing import Dict, Any, AsyncGenerator
import json
import time
import aiosqlite
from pathlib import Path

from tools.file_manager import FileManagerTool
from tools.web_search import WebSearchTool
from tools.code_executor import CodeExecutorTool
from tools.system_monitor import SystemMonitorTool
from tools.process_manager import ProcessManagerTool
from tools.docker_tool import DockerTool
from tools.nginx_tool import NginxTool


class ToolRegistry:
    def __init__(self):
        self.tools = {
            "file_manager": FileManagerTool(),
            "web_search": WebSearchTool(),
            "code_executor": CodeExecutorTool(),
            "system_monitor": SystemMonitorTool(),
            "process_manager": ProcessManagerTool(),
            "docker_control": DockerTool(),
            "nginx_control": NginxTool(),
        }
        self.db_path = Path(__file__).parent.parent / "aria_audit.db"

    def get_claude_definitions(self) -> list:
        """Return tool definitions in Claude's tool_use JSON schema format."""
        definitions = []
        for name, tool in self.tools.items():
            tool_def = tool.get_tool_definition()
            definitions.append({
                "name": name,
                "description": tool_def["description"],
                "input_schema": tool_def["input_schema"]
            })
        return definitions

    async def execute(self, tool_name: str, inputs: Dict[str, Any]) -> Dict:
        """Execute a tool and log to audit database."""
        start_time = time.time()

        if tool_name not in self.tools:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}

        tool = self.tools[tool_name]
        try:
            result = await tool.execute(**inputs)
        except Exception as e:
            result = {"success": False, "error": str(e)}

        # Log to SQLite
        duration_ms = int((time.time() - start_time) * 1000)
        await self._log_audit(tool_name, inputs, result, duration_ms)

        return result

    async def _log_audit(self, tool_name: str, inputs: Dict, result: Dict, duration_ms: int):
        """Log tool execution to SQLite audit table."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS audit_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT,
                        tool_name TEXT,
                        inputs TEXT,
                        result TEXT,
                        duration_ms INTEGER
                    )
                """)
                await db.execute(
                    """INSERT INTO audit_log (timestamp, tool_name, inputs, result, duration_ms)
                       VALUES (datetime('now'), ?, ?, ?, ?)""",
                    (tool_name, json.dumps(inputs), json.dumps(result), duration_ms)
                )
                await db.commit()
        except Exception:
            pass  # Don't fail if audit logging fails


tool_registry = ToolRegistry()
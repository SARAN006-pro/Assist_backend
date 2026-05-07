from typing import Any, Dict, Optional
import docker
from docker.errors import DockerException


class DockerTool:
    def __init__(self):
        try:
            self.client = docker.from_env()
        except DockerException:
            self.client = None

    def get_tool_definition(self) -> Dict:
        return {
            "description": "Manage Docker containers (list, start, stop, logs, exec).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["list", "start", "stop", "logs", "exec", "stats"]},
                    "container": {"type": "string"},
                    "command": {"type": "string"},
                    "lines": {"type": "integer", "default": 100}
                },
                "required": ["action"]
            }
        }

    async def execute(
        self,
        action: str,
        container: Optional[str] = None,
        command: Optional[str] = None,
        lines: int = 100,
        **kwargs
    ) -> Dict:
        if not self.client:
            return {"success": False, "error": "Docker not available"}

        match action:
            case "list":
                return await self._list_containers()
            case "start":
                return await self._start_container(container)
            case "stop":
                return await self._stop_container(container)
            case "logs":
                return await self._get_logs(container, lines)
            case "exec":
                return await self._exec_command(container, command)
            case "stats":
                return await self._get_stats()
            case _:
                return {"success": False, "error": f"Unknown action: {action}"}

    async def _list_containers(self) -> Dict:
        try:
            containers = self.client.containers.list(all=True)
            return {
                "success": True,
                "result": {
                    "containers": [
                        {
                            "id": c.id[:12],
                            "name": c.name,
                            "image": c.image.tags[0] if c.image.tags else c.image.short_id,
                            "status": c.status,
                            "created": c.attrs.get("Created", "")
                        }
                        for c in containers
                    ]
                }
            }
        except DockerException as e:
            return {"success": False, "error": str(e)}

    async def _start_container(self, container_name: str) -> Dict:
        try:
            container = self.client.containers.get(container_name)
            container.start()
            return {"success": True, "result": {"status": "started", "container": container_name}}
        except DockerException as e:
            return {"success": False, "error": str(e)}

    async def _stop_container(self, container_name: str) -> Dict:
        try:
            container = self.client.containers.get(container_name)
            container.stop()
            return {"success": True, "result": {"status": "stopped", "container": container_name}}
        except DockerException as e:
            return {"success": False, "error": str(e)}

    async def _get_logs(self, container_name: str, lines: int) -> Dict:
        try:
            container = self.client.containers.get(container_name)
            logs = container.logs(tail=lines).decode("utf-8")
            return {"success": True, "result": {"container": container_name, "logs": logs[:5000]}}
        except DockerException as e:
            return {"success": False, "error": str(e)}

    async def _exec_command(self, container_name: str, command: str) -> Dict:
        try:
            container = self.client.containers.get(container_name)
            result = container.exec_run(command)
            return {
                "success": True,
                "result": {
                    "container": container_name,
                    "command": command,
                    "output": result.output.decode("utf-8")[:5000],
                    "exit_code": result.exit_code
                }
            }
        except DockerException as e:
            return {"success": False, "error": str(e)}

    async def _get_stats(self) -> Dict:
        try:
            containers = self.client.containers.list()
            stats = []
            for c in containers:
                s = c.stats(stream=False)
                stats.append({
                    "name": c.name,
                    "cpu_percent": s.get("cpu_stats", {}).get("cpu_usage", {}).get("percent", 0),
                    "memory_usage": s.get("memory_stats", {}).get("usage", 0),
                    "memory_limit": s.get("memory_stats", {}).get("limit", 0),
                })
            return {"success": True, "result": {"containers": stats}}
        except DockerException as e:
            return {"success": False, "error": str(e)}
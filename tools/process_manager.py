from typing import Any, Dict, List, Optional
import psutil


class ProcessManagerTool:
    def get_tool_definition(self) -> Dict:
        return {
            "description": "List, inspect, or terminate running processes.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["list", "info", "kill"]},
                    "pid": {"type": "integer"},
                    "name": {"type": "string"},
                    "sort_by": {"type": "string", "enum": ["cpu", "memory", "pid", "name"]},
                    "confirmed": {"type": "boolean", "default": False}
                },
                "required": ["action"]
            }
        }

    async def execute(
        self,
        action: str,
        pid: Optional[int] = None,
        name: Optional[str] = None,
        sort_by: str = "cpu",
        confirmed: bool = False,
        **kwargs
    ) -> Dict:
        match action:
            case "list":
                return await self._list_processes(sort_by)

            case "info":
                if pid:
                    return await self._process_info(pid)
                if name:
                    return await self._process_info_by_name(name)
                return {"success": False, "error": "Either pid or name required"}

            case "kill":
                if pid:
                    return await self._kill_process(pid, confirmed)
                if name:
                    return await self._kill_process_by_name(name, confirmed)
                return {"success": False, "error": "Either pid or name required"}

            case _:
                return {"success": False, "error": f"Unknown action: {action}"}

    async def _list_processes(self, sort_by: str) -> Dict:
        processes = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
            try:
                processes.append({
                    "pid": proc.info["pid"],
                    "name": proc.info["name"],
                    "cpu_percent": proc.info["cpu_percent"],
                    "memory_percent": proc.info["memory_percent"],
                    "status": proc.info["status"],
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        sort_key = {
            "cpu": lambda x: x.get("cpu_percent", 0) or 0,
            "memory": lambda x: x.get("memory_percent", 0) or 0,
            "pid": lambda x: x.get("pid", 0),
            "name": lambda x: x.get("name", "").lower(),
        }.get(sort_by, lambda x: x.get("cpu_percent", 0) or 0)

        processes.sort(key=sort_key, reverse=True)

        return {
            "success": True,
            "result": {
                "processes": processes[:20],
                "total": len(processes),
                "sort_by": sort_by,
            }
        }

    async def _process_info(self, pid: int) -> Dict:
        try:
            proc = psutil.Process(pid)
            with proc.oneshot():
                return {
                    "success": True,
                    "result": {
                        "pid": proc.pid,
                        "name": proc.name(),
                        "status": proc.status(),
                        "cpu_percent": proc.cpu_percent(),
                        "memory_percent": proc.memory_percent(),
                        "num_threads": proc.num_threads(),
                        "cmdline": proc.cmdline(),
                    }
                }
        except psutil.NoSuchProcess:
            return {"success": False, "error": f"Process {pid} not found"}
        except psutil.AccessDenied:
            return {"success": False, "error": f"Access denied to process {pid}"}

    async def _process_info_by_name(self, name: str) -> Dict:
        matches = []
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                if name.lower() in proc.info["name"].lower():
                    matches.append(await self._process_info(proc.info["pid"]))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return {"success": True, "result": {"processes": matches}}

    async def _kill_process(self, pid: int, confirmed: bool) -> Dict:
        # Safety: don't kill system processes
        if pid < 100:
            return {"success": False, "error": "Cannot kill system process with PID < 100"}

        if not confirmed:
            return {
                "success": False,
                "error": f"Confirmation required to kill process {pid}",
                "requires_confirmation": True,
                "pid": pid
            }

        try:
            proc = psutil.Process(pid)
            proc.kill()
            return {"success": True, "result": {"status": "killed", "pid": pid}}
        except psutil.NoSuchProcess:
            return {"success": False, "error": f"Process {pid} not found"}
        except psutil.AccessDenied:
            return {"success": False, "error": f"Access denied to kill process {pid}"}

    async def _kill_process_by_name(self, name: str, confirmed: bool) -> Dict:
        if not confirmed:
            return {
                "success": False,
                "error": f"Confirmation required to kill processes named '{name}'",
                "requires_confirmation": True,
                "name": name
            }

        killed = []
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                if name.lower() in proc.info["name"].lower():
                    proc.kill()
                    killed.append(proc.info["pid"])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return {"success": True, "result": {"status": "killed", "pids": killed}}
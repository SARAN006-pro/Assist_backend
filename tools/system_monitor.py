from typing import Any, Dict, List
import psutil
from datetime import datetime


class SystemMonitorTool:
    def get_tool_definition(self) -> Dict:
        return {
            "description": "Get CPU, RAM, disk, network stats.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "metrics": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["cpu", "ram", "disk", "network", "processes", "all"]},
                        "default": ["all"]
                    }
                },
                "required": ["metrics"]
            }
        }

    async def execute(self, metrics: List[str] = None, **kwargs) -> Dict:
        if not metrics or "all" in metrics:
            metrics = ["cpu", "ram", "disk", "network", "processes"]

        result = {}

        if "cpu" in metrics:
            result["cpu_percent"] = psutil.cpu_percent(interval=0.5)
            result["cpu_count"] = psutil.cpu_count()

        if "ram" in metrics:
            mem = psutil.virtual_memory()
            result["ram_percent"] = mem.percent
            result["ram_used_gb"] = round(mem.used / (1024**3), 2)
            result["ram_total_gb"] = round(mem.total / (1024**3), 2)

        if "disk" in metrics:
            disks = []
            for part in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    disks.append({
                        "mountpoint": part.mountpoint,
                        "total_gb": round(usage.total / (1024**3), 2),
                        "used_gb": round(usage.used / (1024**3), 2),
                        "free_gb": round(usage.free / (1024**3), 2),
                        "percent": usage.percent,
                    })
                except PermissionError:
                    pass
            result["disk"] = disks

        if "network" in metrics:
            net = psutil.net_io_counters()
            result["network_bytes_sent"] = net.bytes_sent
            result["network_bytes_recv"] = net.bytes_recv

        if "processes" in metrics:
            top_procs = []
            for proc in sorted(psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']),
                             key=lambda p: p.info['cpu_percent'] or 0, reverse=True)[:5]:
                try:
                    top_procs.append({
                        "pid": proc.info['pid'],
                        "name": proc.info['name'],
                        "cpu_percent": proc.info['cpu_percent'],
                        "ram_percent": round(proc.info['memory_percent'] or 0, 2)
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            result["top_processes"] = top_procs

        return {"success": True, "result": result}
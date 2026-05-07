from typing import Any, Dict, Optional
import subprocess
from pathlib import Path
from config import settings


class NginxTool:
    def get_tool_definition(self) -> Dict:
        return {
            "description": "View, test, and reload Nginx configuration.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["status", "test", "reload", "config", "logs"]},
                    "lines": {"type": "integer", "default": 50},
                    "config_path": {"type": "string"}
                },
                "required": ["action"]
            }
        }

    async def execute(
        self,
        action: str,
        lines: int = 50,
        config_path: str = None,
        **kwargs
    ) -> Dict:
        config_path = config_path or settings.NGINX_CONFIG_PATH

        match action:
            case "status":
                return await self._get_status()
            case "test":
                return await self._test_config(config_path)
            case "reload":
                return await self._reload(config_path)
            case "config":
                return await self._view_config(config_path)
            case "logs":
                return await self._tail_logs(lines)
            case _:
                return {"success": False, "error": f"Unknown action: {action}"}

    async def _get_status(self) -> Dict:
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "nginx"],
                capture_output=True,
                text=True,
                timeout=5
            )
            is_active = result.returncode == 0
            return {
                "success": True,
                "result": {
                    "status": "running" if is_active else "stopped",
                    "details": result.stdout.strip()
                }
            }
        except FileNotFoundError:
            return {"success": False, "error": "systemctl not found. Is nginx installed?"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _test_config(self, config_path: str) -> Dict:
        if not Path(config_path).exists():
            return {"success": False, "error": f"Config file not found: {config_path}"}

        try:
            result = subprocess.run(
                ["nginx", "-t", "-c", config_path],
                capture_output=True,
                text=True,
                timeout=10
            )
            success = result.returncode == 0
            return {
                "success": success,
                "result": {
                    "output": result.stdout + result.stderr,
                    "valid": success
                }
            }
        except FileNotFoundError:
            return {"success": False, "error": "nginx command not found. Is nginx installed?"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _reload(self, config_path: str) -> Dict:
        test_result = await self._test_config(config_path)
        if not test_result.get("success"):
            return {"success": False, "error": "Config test failed. Cannot reload.", "details": test_result}

        try:
            result = subprocess.run(
                ["nginx", "-s", "reload", "-c", config_path],
                capture_output=True,
                text=True,
                timeout=10
            )
            return {
                "success": result.returncode == 0,
                "result": {"status": "reloaded" if result.returncode == 0 else "failed"}
            }
        except FileNotFoundError:
            return {"success": False, "error": "nginx command not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _view_config(self, config_path: str) -> Dict:
        if not Path(config_path).exists():
            return {"success": False, "error": f"Config file not found: {config_path}"}

        try:
            with open(config_path, "r") as f:
                content = f.read()
            return {"success": True, "result": {"path": config_path, "content": content[:10000]}}
        except PermissionError:
            return {"success": False, "error": "Permission denied reading config"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _tail_logs(self, lines: int) -> Dict:
        log_paths = ["/var/log/nginx/access.log", "/var/log/nginx/error.log"]
        results = {}

        for log_type, log_path in [("access", log_paths[0]), ("error", log_paths[1])]:
            try:
                if Path(log_path).exists():
                    with open(log_path, "r") as f:
                        all_lines = f.readlines()
                        results[log_type] = "".join(all_lines[-lines:])
                else:
                    results[log_type] = f"Log file not found: {log_path}"
            except PermissionError:
                results[log_type] = "Permission denied"
            except Exception as e:
                results[log_type] = str(e)

        return {"success": True, "result": results}
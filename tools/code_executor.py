from typing import Any, Dict
import asyncio
import time
import docker
from config import settings


class CodeExecutorTool:
    def __init__(self):
        try:
            self.docker_client = docker.from_env()
        except Exception:
            self.docker_client = None

    def get_tool_definition(self) -> Dict:
        return {
            "description": "Run Python or bash code in a safe Docker sandbox.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "language": {"type": "string", "enum": ["python", "bash"]},
                    "timeout": {"type": "integer", "default": 30}
                },
                "required": ["code"]
            }
        }

    async def execute(
        self,
        code: str,
        language: str = "python",
        timeout: int = None,
        **kwargs
    ) -> Dict:
        timeout = timeout or settings.SANDBOX_TIMEOUT
        start_time = time.time()

        if not self.docker_client:
            return await self._execute_local(code, language, timeout, start_time)

        return await self._execute_docker(code, language, timeout, start_time)

    async def _execute_docker(self, code: str, language: str, timeout: int, start_time: float) -> Dict:
        image = settings.SANDBOX_IMAGE

        if language == "python":
            cmd = ["python", "-c", code]
        else:
            cmd = ["bash", "-c", code]

        try:
            container = self.docker_client.containers.run(
                image,
                cmd,
                detach=True,
                mem_limit="256m",
                cpu_period=100000,
                cpu_quota=50000,
                network_disabled=True,
                remove=True,
                timeout=timeout,
            )

            result = container.wait(timeout=timeout)
            logs = container.logs(stdout=True, stderr=True).decode("utf-8")

            duration_ms = int((time.time() - start_time) * 1000)

            return {
                "success": True,
                "result": {
                    "stdout": logs[:5000],
                    "stderr": "",
                    "exit_code": result.StatusCode,
                    "duration_ms": duration_ms
                }
            }
        except docker.errors.NotFound:
            return {"success": False, "error": f"Docker image '{image}' not found"}
        except docker.errors.ContainerError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _execute_local(self, code: str, language: str, timeout: int, start_time: float) -> Dict:
        import tempfile
        import subprocess

        duration_ms = 0

        if language == "python":
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(code)
                temp_file = f.name

            try:
                result = subprocess.run(
                    ["python", temp_file],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                duration_ms = int((time.time() - start_time) * 1000)
                return {
                    "success": True,
                    "result": {
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "exit_code": result.returncode,
                        "duration_ms": duration_ms
                    }
                }
            except subprocess.TimeoutExpired:
                return {"success": False, "error": "Execution timed out"}
            finally:
                import os
                os.unlink(temp_file)

        elif language == "bash":
            try:
                result = subprocess.run(
                    ["bash", "-c", code],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                duration_ms = int((time.time() - start_time) * 1000)
                return {
                    "success": True,
                    "result": {
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "exit_code": result.returncode,
                        "duration_ms": duration_ms
                    }
                }
            except subprocess.TimeoutExpired:
                return {"success": False, "error": "Execution timed out"}

        return {"success": False, "error": f"Language '{language}' execution not supported locally"}
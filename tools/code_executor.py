from typing import Any, Dict
import time
import tempfile
import subprocess
import os
from config import settings


class CodeExecutorTool:
    def get_tool_definition(self) -> Dict:
        return {
            "description": "Run Python or bash code securely.",
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

        if language == "python":
            return await self._execute_python(code, timeout, start_time)
        elif language == "bash":
            return await self._execute_bash(code, timeout, start_time)

        return {"success": False, "error": f"Language '{language}' not supported"}

    async def _execute_python(self, code: str, timeout: int, start_time: float) -> Dict:
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
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            try:
                os.unlink(temp_file)
            except:
                pass

    async def _execute_bash(self, code: str, timeout: int, start_time: float) -> Dict:
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
        except Exception as e:
            return {"success": False, "error": str(e)}
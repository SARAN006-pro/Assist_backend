import os
from typing import Any, Dict, Optional
from pathlib import Path
import aiofiles
import shutil
from config import settings


class FileManagerTool:
    def __init__(self):
        self.allowed_dirs = settings.ALLOWED_BASE_DIRS

    def _is_allowed(self, path: str) -> bool:
        """Check if path is within allowed directories."""
        abs_path = os.path.abspath(path)
        for allowed in self.allowed_dirs:
            if abs_path.startswith(allowed):
                return True
        return False

    def get_tool_definition(self) -> Dict:
        return {
            "description": "Create, read, move, copy, delete files and directories on the local system.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["read", "write", "move", "copy", "delete", "list", "mkdir", "search"]
                    },
                    "path": {"type": "string"},
                    "destination": {"type": "string"},
                    "content": {"type": "string"},
                    "recursive": {"type": "boolean", "default": False}
                },
                "required": ["action", "path"]
            }
        }

    async def execute(
        self,
        action: str,
        path: str,
        destination: Optional[str] = None,
        content: Optional[str] = None,
        recursive: bool = False,
        **kwargs
    ) -> Dict:
        # Security check
        if not self._is_allowed(path):
            return {"success": False, "error": f"Path '{path}' not in allowed directories: {self.allowed_dirs}"}

        file_path = Path(path)

        match action:
            case "list":
                if not file_path.exists():
                    return {"success": False, "error": f"Path '{path}' does not exist"}
                if file_path.is_file():
                    return {"success": False, "error": "Path is a file, not a directory"}

                items = []
                for item in file_path.iterdir():
                    items.append({
                        "name": item.name,
                        "type": "directory" if item.is_dir() else "file",
                        "size": item.stat().st_size if item.is_file() else 0,
                    })
                return {"success": True, "result": {"path": str(file_path), "items": items}}

            case "read":
                if not file_path.exists():
                    return {"success": False, "error": f"File '{path}' does not exist"}
                if file_path.is_dir():
                    return {"success": False, "error": "Path is a directory"}

                try:
                    async with aiofiles.open(file_path, "r") as f:
                        file_content = await f.read()
                    return {"success": True, "result": {"path": str(file_path), "content": file_content[:10000]}}
                except UnicodeDecodeError:
                    async with aiofiles.open(file_path, "rb") as f:
                        file_content = await f.read()
                    return {"success": True, "result": {"path": str(file_path), "content": "[Binary file]"}}

            case "write":
                file_path.parent.mkdir(parents=True, exist_ok=True)
                async with aiofiles.open(file_path, "w") as f:
                    await f.write(content or "")
                return {"success": True, "result": {"status": "written", "path": str(file_path)}}

            case "delete":
                if not file_path.exists():
                    return {"success": False, "error": f"Path '{path}' does not exist"}
                if file_path.is_file():
                    file_path.unlink()
                else:
                    shutil.rmtree(file_path)
                return {"success": True, "result": {"status": "deleted", "path": str(file_path)}}

            case "mkdir":
                file_path.mkdir(parents=True, exist_ok=True)
                return {"success": True, "result": {"status": "created", "path": str(file_path)}}

            case "move":
                if not file_path.exists():
                    return {"success": False, "error": f"Source '{path}' does not exist"}
                dest_path = Path(destination)
                if not self._is_allowed(str(dest_path)):
                    return {"success": False, "error": f"Destination not in allowed directories"}
                shutil.move(str(file_path), str(dest_path))
                return {"success": True, "result": {"status": "moved", "from": str(file_path), "to": str(dest_path)}}

            case "copy":
                if not file_path.exists():
                    return {"success": False, "error": f"Source '{path}' does not exist"}
                dest_path = Path(destination)
                if not self._is_allowed(str(dest_path)):
                    return {"success": False, "error": f"Destination not in allowed directories"}
                if file_path.is_file():
                    shutil.copy2(str(file_path), str(dest_path))
                else:
                    shutil.copytree(str(file_path), str(dest_path))
                return {"success": True, "result": {"status": "copied", "from": str(file_path), "to": str(dest_path)}}

            case "search":
                if not file_path.exists():
                    return {"success": False, "error": f"Path '{path}' does not exist"}
                if not file_path.is_dir():
                    return {"success": False, "error": "Path must be a directory for search"}

                pattern = kwargs.get("pattern", "*")
                results = []
                if recursive:
                    for item in file_path.rglob(pattern):
                        results.append({
                            "name": item.name,
                            "path": str(item),
                            "type": "directory" if item.is_dir() else "file"
                        })
                else:
                    for item in file_path.glob(pattern):
                        results.append({
                            "name": item.name,
                            "path": str(item),
                            "type": "directory" if item.is_dir() else "file"
                        })
                return {"success": True, "result": {"path": str(file_path), "pattern": pattern, "results": results[:100]}}

            case _:
                return {"success": False, "error": f"Unknown action: {action}"}
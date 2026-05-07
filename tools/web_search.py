from typing import Any, Dict
from duckduckgo_search import DDGS


class WebSearchTool:
    def __init__(self):
        self.ddgs = DDGS()

    def get_tool_definition(self) -> Dict:
        return {
            "description": "Search the internet and return summarized results.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer", "default": 5}
                },
                "required": ["query"]
            }
        }

    async def execute(self, query: str, max_results: int = 5, **kwargs) -> Dict:
        try:
            results = self.ddgs.text(query, max_results=max_results)
            return {
                "success": True,
                "result": {
                    "query": query,
                    "results": [
                        {
                            "title": r.get("title", ""),
                            "url": r.get("href", ""),
                            "snippet": r.get("body", "")
                        }
                        for r in results
                    ],
                    "total": len(results) if results else 0
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
from typing import Dict, Any, AsyncGenerator, List
import json
import logging
from openai import AsyncOpenAI
from core.session import session_manager
from core.tools import tool_registry
from config import settings

logger = logging.getLogger("aria")


SYSTEM_PROMPT = """You are ARIA (Autonomous Resource & Intelligence Assistant), a powerful personal AI
assistant with direct access to the user's local device, file system, and tools.

Identity:
- Address the user as "Sir" unless they specify otherwise
- Be precise, efficient, and direct — no filler phrases like "Certainly!" or "Of course!"
- Always confirm before: deleting files, killing processes, running destructive commands
- After multi-step tasks, give a short numbered summary of what you did

Capabilities you can invoke:
1. file_manager — create, read, move, copy, delete files and directories
2. web_search — search the internet and return summarized results
3. code_executor — run Python or bash code securely
4. system_monitor — get CPU, RAM, disk, network stats
5. process_manager — list, inspect, or terminate running processes
6. screen_capture — take screenshots and describe what is on screen

Safety rules (non-negotiable):
- NEVER delete files without explicit user confirmation
- NEVER kill a process with PID < 100 (system processes)
- NEVER run dangerous commands
- ALWAYS explain what a command will do before doing it if it's destructive
- Log every tool action

Response format:
- Single action: 1-2 sentences confirming what was done
- Multi-step: numbered list summary at end
- Error: what failed, likely reason, what to try next
- Voice mode: max 2 sentences, no code blocks, no file paths
"""


class Orchestrator:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url=settings.GROQ_BASE_URL
        )
        self.model = settings.GROQ_MODEL
        self.max_tokens = settings.GROQ_MAX_TOKENS

    async def stream(
        self,
        user_message: str,
        session_id: str,
        voice_mode: bool = False
    ) -> AsyncGenerator[str, None]:
        """Stream AI response with tool calls."""
        logger.info(f"Processing message for session {session_id}")

        try:
            history = await session_manager.get_history(session_id)
        except Exception as e:
            logger.error(f"Failed to load history: {e}")
            history = []

        messages = [{"role": "user", "content": user_message}]
        for msg in history:
            messages.insert(0, {"role": msg["role"], "content": msg["content"]})

        tools = tool_registry.get_claude_definitions()

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
                tools=tools,
                stream=True
            )
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            yield json.dumps({"type": "error", "content": f"AI service error: {str(e)}"})
            yield json.dumps({"type": "done"})
            return

        tool_calls = []
        text_content = []

        # Stream the response
        async for chunk in response:
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta

                # Handle text content
                if delta.content:
                    text_content.append(delta.content)
                    yield json.dumps({"type": "text", "content": delta.content})

                # Handle tool calls
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        while len(tool_calls) <= tc.index:
                            tool_calls.append({"name": "", "input": {}})
                        if tc.function.name:
                            tool_calls[tc.index]["name"] = tc.function.name
                        if tc.function.arguments:
                            try:
                                args = json.loads(tc.function.arguments)
                                tool_calls[tc.index]["input"].update(args)
                            except:
                                pass

        # Check if we need to call tools
        if tool_calls and any(tc.get("name") for tc in tool_calls):
            for tc in tool_calls:
                tool_name = tc.get("name")
                if not tool_name:
                    continue
                tool_input = tc.get("input", {})

                yield json.dumps({
                    "type": "tool_start",
                    "tool": tool_name,
                    "input": tool_input
                })

                try:
                    result = await tool_registry.execute(tool_name, tool_input)
                    logger.info(f"Tool {tool_name} executed successfully")
                except Exception as e:
                    logger.error(f"Tool {tool_name} failed: {e}")
                    result = {"error": str(e)}

                yield json.dumps({
                    "type": "tool_result",
                    "tool": tool_name,
                    "result": result
                })

                messages.append({
                    "role": "user",
                    "content": f"Tool {tool_name} returned: {json.dumps(result)}"
                })

            try:
                follow_up = await self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
                    stream=True
                )

                async for chunk in follow_up:
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        if delta.content:
                            text_content.append(delta.content)
                            yield json.dumps({"type": "text", "content": delta.content})
            except Exception as e:
                logger.error(f"Follow-up AI call failed: {e}")

        try:
            history.append({"role": "user", "content": user_message})
            history.append({"role": "assistant", "content": "".join(text_content)})
            await session_manager.save_history(session_id, history)
        except Exception as e:
            logger.warning(f"Failed to save history: {e}")

        yield json.dumps({"type": "done"})
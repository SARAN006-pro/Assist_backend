from fastapi import APIRouter, WebSocket
from tools.system_monitor import SystemMonitorTool
from tools.process_manager import ProcessManagerTool
import asyncio

router = APIRouter()
system_tool = SystemMonitorTool()
process_tool = ProcessManagerTool()


@router.get("/metrics")
async def get_metrics():
    """Get current system metrics."""
    return await system_tool.execute(metrics=["all"])


@router.get("/processes")
async def get_processes():
    """Get top 20 processes."""
    result = await process_tool.execute(action="list", sort_by="cpu")
    return result


@router.websocket("/ws/system/live")
async def websocket_system_live(websocket: WebSocket):
    """WebSocket for live system metrics."""
    await websocket.accept()

    try:
        while True:
            metrics = await system_tool.execute(metrics=["cpu", "ram", "disk", "network", "processes"])
            await websocket.send_json(metrics)
            await asyncio.sleep(2)
    except Exception:
        pass
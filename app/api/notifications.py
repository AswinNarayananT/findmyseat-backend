from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from app.core.notifications import manager
from uuid import UUID

router = APIRouter(prefix="/notifications", tags=["Notifications"])

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(user_id)
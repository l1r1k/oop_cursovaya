import logging
import os
import uuid

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

CORS_ORIGINS = os.getenv(
    'WS_CORS_ORIGINS',
    'http://localhost:8000,http://127.0.0.1:8000,http://localhost:3000',
).split(',')

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in CORS_ORIGINS if origin.strip()],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

DJANGO_API_URL = os.getenv('DJANGO_API_URL', 'http://127.0.0.1:8000').rstrip('/')

active_clients: dict[str, WebSocket] = {}
TYPE_MSG = ['AUTH', 'REG', 'MSG', 'READ']


def _remove_client(client_id: str | None) -> None:
    if client_id:
        active_clients.pop(client_id, None)


async def _save_message_to_db(ticket_id: int, msg: str, sender_id: str, media_urls: list | None = None) -> dict | None:
    url = f'{DJANGO_API_URL}/api/support/ticket/message/create/'
    payload = {
        'ticket_id': ticket_id,
        'msg': msg or '',
        'sender_id': sender_id,
    }
    if media_urls:
        payload['media'] = media_urls
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
        if response.status_code == 200:
            return response.json()
        logger.warning('API save failed: %s %s', response.status_code, response.text)
    except httpx.HTTPError as exc:
        logger.error('API request error: %s', exc)
    return None


async def _send_to_client(client_id: str | None, payload: dict) -> None:
    if not client_id:
        return
    websocket = active_clients.get(client_id)
    if not websocket:
        return
    try:
        await websocket.send_json(payload)
    except Exception as exc:
        logger.error('Error sending to %s: %s', client_id, exc)
        _remove_client(client_id)


@app.websocket('/ws')
async def connect(websocket: WebSocket):
    await websocket.accept()
    client_id = None

    try:
        while True:
            request = await websocket.receive_json()

            if not isinstance(request, dict):
                logger.warning('Invalid request type')
                continue

            msg_type = request.get('type')

            if msg_type == TYPE_MSG[0]:  # AUTH
                client_id = request.get('id')
                if client_id:
                    active_clients[str(client_id)] = websocket
                    logger.info('Client authenticated: %s', client_id)

            elif msg_type == TYPE_MSG[1]:  # REG
                client_id = str(uuid.uuid4())
                active_clients[client_id] = websocket
                await websocket.send_json({
                    'id': client_id,
                    'type': 'REG',
                })
                logger.info('New client registered: %s', client_id)

            elif msg_type == TYPE_MSG[2]:  # MSG
                ticket_id = request.get('ticket_id')
                msg_text = (request.get('msg') or '').strip()
                sender_id = request.get('from')
                to_client = request.get('to')

                has_media = bool(request.get('media'))
                if not ticket_id or not sender_id:
                    await websocket.send_json({
                        'type': 'ERROR',
                        'error': 'ticket_id и from обязательны',
                    })
                    continue

                if not request.get('msg_id') and not msg_text and not has_media:
                    await websocket.send_json({
                        'type': 'ERROR',
                        'error': 'Укажите текст или медиа',
                    })
                    continue

                if not request.get('msg_id'):
                    saved = await _save_message_to_db(
                        int(ticket_id),
                        msg_text,
                        str(sender_id),
                        request.get('media'),
                    )
                    if not saved:
                        await websocket.send_json({
                            'type': 'ERROR',
                            'error': 'Не удалось сохранить сообщение',
                        })
                        continue
                    request['msg_id'] = saved.get('msg_id')
                    request['datetime'] = saved.get('datetime')
                    request.setdefault('msg', saved.get('msg', msg_text))
                    request.setdefault('media', saved.get('media', []))
                    request.setdefault('support_uuid', saved.get('support_uuid'))
                    request.setdefault('renter_uuid', saved.get('renter_uuid'))

                request['type'] = 'MSG'
                await _send_to_client(to_client, request)
                if str(sender_id) != str(to_client):
                    await _send_to_client(str(sender_id), request)

            elif msg_type == TYPE_MSG[3]:  # READ
                await websocket.send_json({
                    'type': 'READ',
                    'all_active_users': list(active_clients.keys()),
                })

    except WebSocketDisconnect:
        _remove_client(client_id)
        logger.info('Client disconnected: %s', client_id)

    except Exception as exc:
        logger.error('WebSocket error: %s', exc)
        _remove_client(client_id)

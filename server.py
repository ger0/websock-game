from fastapi import FastAPI, WebSocket
from enum import Enum
import struct


State = Enum('State', ['EMPTY', 'BLACK', 'WHITE'])
MAP_S = 8


class Board:
    def __init__(self):
        self.data = [State.BLACK] * (MAP_S * MAP_S)

    def put(self, x: int, y: int, state: State):
        self.data[x + y * MAP_S] = state

    # converts an array of States into an array of bytes
    def get_bytes(self):
        return [i.value.to_bytes(1)[0] for i in self.data]


app = FastAPI()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    board = Board()
    data = [MAP_S, *board.get_bytes()]
    data = struct.pack('!{}b'.format(len(data)), *data)

    await websocket.send_bytes(data)


@app.get("/config")
async def send_json():
    with open("config.json", "r") as file:
        data = file.read()
        return data

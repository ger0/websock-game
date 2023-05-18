from fastapi import FastAPI, WebSocket
from enum import Enum
import struct
import json

# default values
MAP_S = 8
C_COLS = ['red', 'black']
C_SIZE = 35

app = FastAPI()


# entry point
def main():
    load_config('config.json')
    manager = ConnectionManager()

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await manager.connect(websocket)


class State(Enum):
    EMPTY = 0
    BLACK = 1
    WHITE = 2


class Request(Enum):
    CONFIG = 0
    UPDATE = 1
    DRAW = 2


class Board:
    def __init__(self):
        self.data = [State.EMPTY] * (MAP_S * MAP_S)
        self.data[0] = State.BLACK
        self.data[9] = State.BLACK
        self.data[18] = State.WHITE

    def put(self, x: int, y: int, state: State):
        self.data[x + y * MAP_S] = state

    # converts an array of States(ints) into an array of single bytes
    def get_bytes(self):
        return [i.value.to_bytes(1)[0] for i in self.data]


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.active_boards: dict[WebSocket, Board] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        board = Board()
        self.active_boards[websocket] = board
        await self.send_board(board, websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_board(self, board: Board, websocket: WebSocket):
        data = board.get_bytes()
        data = struct.pack('!{}b'.format(len(data)), *data)
        await websocket.send_bytes(data)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


def load_config(filename):
    global MAP_S, C_COLS, C_SIZE
    with open(filename, 'r') as file:
        data = json.load(file)
        MAP_S = data['map_dimensions']
        C_COLS = data['colours']
        C_SIZE = data['circle_size']


if __name__ == "server":
    main()

from fastapi import FastAPI, WebSocket
from enum import Enum
import struct
import json


# default values
class Config:
    map_dimensions = 8
    circle_colours = ['red', 'black']
    circle_size = 35


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

    def to_byte(self):
        return self.value.to_bytes(1)[0]


class Request(Enum):
    CONFIGURE_GAME = 0
    UPDATE_BOARD = 1
    LOAD_WHOLE_BOARD = 2

    def to_byte(self):
        return self.value.to_bytes(1)[0]


class Move_Update():
    request: Request
    x: int
    y: int

    def __init__(self, x: bytes, y: bytes, request: Request):
        self.request = request
        self.x = x
        self.y = y

    def to_array(self):
        return [
            self.x.to_bytes(1)[0],
            self.y.to_bytes(1)[0],
            self.request.to_byte()
        ]


class Board:
    def __init__(self):
        self.data = [State.EMPTY] * (conf.map_dimensions * conf.map_dimensions)

    def put(self, x: bytes, y: bytes, state: State):
        self.data[x + y * conf.map_dimensions] = state

    # converts an array of States(ints) into an array of single bytes
    def to_array(self):
        return [i.to_byte() for i in self.data]


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.active_boards: dict[WebSocket, Board] = {}

    # if the game exists already, send player a previous state of the board
    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active_connections.append(ws)
        await self.send_config(conf, ws)
        board = Board()
        self.active_boards[ws] = board
        await self.send_board(board, ws)
        while True:
            data = await ws.receive_bytes()
            opcode = data[0]
            if (opcode == Request.UPDATE_BOARD.value):
                print("RECEIVED PACKET", Request(opcode))
                update = Move_Update(data[1], data[2], Request(opcode))
                # self.active_boards[ws].put(data[1], data[2], State.BLACK)
                # await self.send_board(self.active_boards[ws], ws)
                await self.send_board_update(update, ws)

    def disconnect(self, ws: WebSocket):
        self.active_connections.remove(ws)

    async def send_config(self, config: Config, ws: WebSocket):
        data = json.dumps(config.__dict__)
        data = bytearray(data, 'ascii')
        await self.send(Request.CONFIGURE_GAME, data, ws)

    async def send_board(self, board: Board, ws: WebSocket):
        data = board.to_array()
        await self.send(Request.LOAD_WHOLE_BOARD, data, ws)

    async def send_board_update(self, move: Move_Update, ws: WebSocket):
        data = move.to_array()
        await self.send(Request.UPDATE_BOARD, data, ws)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

    async def send(self, req: Request, bytes, ws: WebSocket):
        data = [req.to_byte(), *bytes]
        data = struct.pack('!{}b'.format(len(data)), *data)
        await ws.send_bytes(data)


def load_config(filename):
    global conf
    with open(filename, 'r') as file:
        data = json.load(file)
        conf = Config()
        conf.map_dimensions = data['map_dimensions']
        conf.circle_colours = data['colours']
        conf.circle_size = data['circle_size']


if __name__ == "server":
    main()

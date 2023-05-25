from fastapi import FastAPI, WebSocket, WebSocketDisconnect
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

    def next_turn(self):
        if self == State.BLACK:
            self = State.WHITE
        elif self == State.WHITE:
            self = State.BLACK
        return self


class Request(Enum):
    CONFIGURE_GAME = 0
    UPDATE_BOARD = 1
    LOAD_WHOLE_BOARD = 2
    RECV_SESSION_ID = 3
    SEND_SESSION_ID = 4
    NEW_SESSION = 5

    def to_byte(self):
        return self.value.to_bytes(1)[0]


class Move_Update():
    state: State
    x: int
    y: int

    def __init__(self, x: bytes, y: bytes):
        self.x = x
        self.y = y

    def to_array(self):
        return [
            self.x.to_bytes(1)[0],
            self.y.to_bytes(1)[0],
            self.state.to_byte()
        ]


class Board:
    def __init__(self):
        self.data = [State.EMPTY] * (conf.map_dimensions * conf.map_dimensions)

    def put(self, m: Move_Update, state: State):
        self.data[m.x + m.y * conf.map_dimensions] = state

    # converts an array of States(ints) into an array of single bytes
    def to_array(self):
        return [i.to_byte() for i in self.data]


class Connection:
    counter = 0
    ws = {State.WHITE: None, State.BLACK: None}
    board = None
    turn = State.WHITE

    def __init__(self):
        self.board = Board()

    async def send_config(self, ws):
        global conf
        data = json.dumps(conf.__dict__)
        data = bytearray(data, 'ascii')
        await self.send(Request.CONFIGURE_GAME, data, ws)

    async def connect(self, ws):
        # self.ws = [ws if i is None else i for i in self.ws]
        for i in self.ws:
            if self.ws[i] is None:
                self.ws[i] = ws
                break
        self.counter += 1
        await self.send_config(ws)
        await self.send_board(ws)

    def disconnect(self, ws):
        # self.ws = [None if i == ws else i for i in self.ws]
        for i in self.ws:
            if self.ws[i] is ws:
                self.ws[i] = None
                self.counter -= 1

    def is_active(self):
        if self.counter == 0:
            return False
        return True

    async def send_board(self, ws):
        data = self.board.to_array()
        await self.send(Request.LOAD_WHOLE_BOARD, data, ws)

    async def update_board(self, move: Move_Update, ws: WebSocket):
        colour = None
        for i in self.ws:
            if self.ws[i] == ws:
                colour = i

        # skip invalid turns
        if colour == self.turn:
            return

        self.board.put(move, colour)
        move.state = colour
        data = move.to_array()
        await self.broadcast(Request.UPDATE_BOARD, data)
        self.turn = self.turn.next_turn()

    async def send_session_id(self, session_id: int, ws: WebSocket):
        data = session_id.to_bytes()
        await self.send(Request.SEND_SESSION_ID, data, ws)

    async def send(self, req: Request, bytes, ws: WebSocket):
        data = [req.to_byte(), *bytes]
        data = struct.pack('!{}b'.format(len(data)), *data)
        await ws.send_bytes(data)

    async def broadcast(self, req: Request, bytes):
        for it in self.ws:
            if self.ws[it] is None:
                continue
            await self.send(req, bytes, self.ws[it])
            print(f"Sent to {self.ws[it]}")


class ConnectionManager:
    def __init__(self):
        self.sessions: dict[int, Connection] = {}
        self.ws_to_session: dict[WebSocket, int] = {}

    async def run(self, ws: WebSocket):
        con = None
        while True:
            data = await ws.receive_bytes()
            opcode = data[0]
            data = data[1:]
            if (not con and opcode == Request.NEW_SESSION.value):
                con = Connection()
                await con.connect(ws)
                if (self.sessions):
                    keys = list(self.sessions.keys())
                    print(keys)
                    session_id = keys[-1] + 1
                else:
                    session_id = 1
                self.sessions[session_id] = con
                self.ws_to_session[ws] = session_id
                await con.send_session_id(session_id, ws)

            if (not con and opcode == Request.RECV_SESSION_ID.value):
                # TODO: convert to an actual integer
                session_id = int.from_bytes(data)
                print(f"RECEIVED SESSIONID {session_id}")
                if session_id not in self.sessions.keys():
                    con = Connection()
                    self.sessions[session_id] = con
                    self.ws_to_session[ws] = session_id
                else:
                    con = self.sessions[session_id]
                    self.ws_to_session[ws] = session_id
                await con.connect(ws)
                await con.send_board(ws)

            if (con and opcode == Request.UPDATE_BOARD.value):
                print(f"RECEIVED PACKET {Request.UPDATE_BOARD}, session: {self.ws_to_session[ws]}")
                (x, y) = (data[0], data[1])
                update = Move_Update(x, y)
                await con.update_board(update, ws)

    # if the game exists already, send player a previous state of the board
    async def connect(self, ws: WebSocket):
        await ws.accept()
        try:
            # main loop
            await self.run(ws)
        except WebSocketDisconnect:
            self.disconnect(ws)

    def disconnect(self, ws: WebSocket):
        session = self.ws_to_session.pop(ws)
        con = self.sessions[session]
        con.disconnect(ws)
        if con.is_active() is False:
            self.sessions.pop(session)
        print(f"Disconnected {ws}")


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

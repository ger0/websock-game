from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import struct
import json
from utils import State, Move_Update, Request, Config


app = FastAPI()
app.mount("/static", StaticFiles(directory="."), name="static")

global conf


# entry point
def main():
    global conf
    conf = load_config('config.json')
    html_page = load_html('index.html')
    manager = ConnectionManager()

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await manager.connect(websocket)

    @app.get("/", response_class=HTMLResponse)
    def return_html():
        return html_page

    @app.get("/favicon.ico", include_in_schema=False)
    def return_favicon():
        return "No favicon"


class Board:
    def __init__(self):
        self.data = [State.EMPTY] * (conf.map_dimensions * conf.map_dimensions)

    def put(self, m: Move_Update, state: State):
        self.data[m.x + m.y * conf.map_dimensions] = state

    # converts an array of States(ints) into an array of single bytes
    def to_array(self):
        return [i.to_byte() for i in self.data]


class Session:
    counter = 0
    ws = {State.WHITE: None, State.BLACK: None}
    board = None
    turn = State.WHITE

    def __init__(self):
        self.board = Board()

    async def send_config(self, colour: State, ws: WebSocket):
        config = conf
        config.this_colour = colour.value
        data = json.dumps(config.__dict__)
        data = bytearray(data, 'ascii')
        await self.send(Request.CONFIGURE_GAME, data, ws)

    async def connect(self, ws):
        colour = None
        for i in self.ws:
            if self.ws[i] is None:
                self.ws[i] = ws
                colour = i
                self.counter += 1
                break
        await self.send_config(colour, ws)
        await self.send_board(ws)

    def disconnect(self, ws):
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
        colour = self.turn
        print(f"Current turn: {self.turn}")
        if self.counter != 2 or ws != self.ws[colour]:
            curr = None
            for i in self.ws:
                if self.ws[i] == ws:
                    curr = i
            print(f"Colour: {curr}, Expected: {colour}")
            print(f"Denied update! connections: {self.counter}, \
            sent: {ws}, expected: {self.ws[colour]}")
            return

        self.board.put(move, colour)
        move.state = colour
        data = move.to_array()
        await self.broadcast(Request.UPDATE_BOARD, data)
        self.turn = self.turn.next_turn()
        print(f"[{ws.url.port}] Updated! :{self.turn}")

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
        self.sessions: dict[int, Session] = {}
        self.ws_to_session: dict[WebSocket, int] = {}

    async def run(self, ws: WebSocket):
        session = None
        while True:
            data = await ws.receive_bytes()
            request = Request(data[0])
            data = data[1:]
            if (not session and request == Request.NEW_SESSION):
                session = Session()
                await session.connect(ws)
                if (self.sessions):
                    keys = list(self.sessions.keys())
                    print(keys)
                    session_id = keys[-1] + 1
                else:
                    session_id = 1
                self.sessions[session_id] = session
                self.ws_to_session[ws] = session_id
                await session.send_session_id(session_id, ws)

            if (not session and request == Request.RECV_SESSION_ID):
                session_id = int.from_bytes(data)
                print(f"RECEIVED SESSIONID {session_id}")
                if session_id not in self.sessions.keys():
                    session = Session()
                    self.sessions[session_id] = session
                    self.ws_to_session[ws] = session_id
                else:
                    session = self.sessions[session_id]
                    self.ws_to_session[ws] = session_id
                await session.connect(ws)
                await session.send_board(ws)

            if (session and request == Request.UPDATE_BOARD):
                print(f"RECEIVED {request}, session: {self.ws_to_session[ws]}")
                (x, y) = (data[0], data[1])
                update = Move_Update(x, y)
                await session.update_board(update, ws)

    # if the game exists already, send the player a previous state of the board
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
    with open(filename, 'r') as file:
        data = json.load(file)
        conf = Config()
        conf.map_dimensions = data['map_dimensions']
        conf.circle_colours = data['colours']
        conf.circle_size = data['circle_size']
        return conf


def load_html(filename):
    with open(filename, 'r') as file:
        html = file.read()
        return html


if __name__ == "server":
    main()

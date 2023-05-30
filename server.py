import struct
import json
import secrets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from utils import State, Move_Update, Opcode, Config


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
    groups = {State.WHITE: [], State.BLACK: []}
    score = {State.WHITE: 0, State.BLACK: 0}

    def __init__(self):
        self.data = [State.EMPTY] * (conf.map_dimensions * conf.map_dimensions)

    def iter(self, x: int, y: int):
        if not (0 <= x < conf.map_dimensions and 0 <= y < conf.map_dimensions):
            return None
        return x + y * (conf.map_dimensions)

    # returns a dictionary containing position entries for two colour types
    def get_neighbours(self, x: int, y: int):
        neighbours = {State.WHITE: [], State.BLACK: [], State.EMPTY: []}
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        for dx, dy in directions:
            (nx, ny) = (x + dx, y + dy)
            idx = self.iter(nx, ny)
            if (idx is None):
                continue
            state = self.data[idx]
            neighbours[state].append((nx, ny))
        return neighbours

    def merge_groups(self, new_pos: (int, int), state: State):
        neighbours = self.get_neighbours(new_pos[0], new_pos[1])
        groups = self.groups[state]
        merge_idxs = []
        # find groups to which the neighbours belong to and try to join them
        # we don't want any duplicates in our set of positions
        merge_group = set()
        for pos in neighbours[state]:
            for i, _ in enumerate(groups):
                if pos in groups[i]:
                    merge_idxs.append(i)
                    merge_group.update(groups[i])
        for idx in merge_idxs:
            groups = [groups[i] for i, _ in enumerate(groups) if i not in merge_idxs]

        # print(f"Pos: {new_pos} inserted in a group of: {merge_group}!")
        merge_group.add(new_pos)
        groups.append(merge_group)
        self.groups[state] = groups

    def remove_group(self, group_idcs: int, state: State):
        removed_poses = []
        for idx in group_idcs:
            poses = self.groups[state].pop(idx)
            for pos in poses:
                iter = self.iter(pos[0], pos[1])

                self.data[iter] = State.EMPTY
                removed_poses.append(pos)
        self.score[state.next_turn()] += len(removed_poses)
        return removed_poses if len(removed_poses) > 0 else None

    # checks if any of the groups of the enemys colour lack an empty space
    def get_encircled_positions(self, state: State):
        # enemys colour
        colour = state.next_turn()
        removed_groups = []
        for i, group in enumerate(self.groups[colour]):
            empty_spaces = 0
            for pos in group:
                neighbours = self.get_neighbours(pos[0], pos[1])
                empty_spaces += len(neighbours[State.EMPTY])
                # print(f"empty space for {pos}, {neighbours[State.EMPTY]}")
            # print(f"{group}, {empty_spaces}")
            if empty_spaces == 0:
                # print(f"ENCIRCLED GROUP {i}{group}")
                removed_groups.append(i)
        # returns all removed positions
        return self.remove_group(removed_groups, colour)

    def put(self, m: Move_Update):
        self.merge_groups((m.x, m.y), m.state)
        self.data[self.iter(m.x, m.y)] = m.state

    # converts an array of States(ints) into an array of single bytes
    def to_array(self):
        return [i.to_byte() for i in self.data]


class Session:
    def __init__(self, id: int):
        self.counter = 0
        self.board = Board()
        self.tokens = [None] * 2
        self.turn = State.WHITE
        self.ws = {State.WHITE: None, State.BLACK: None}
        self.id = id

    async def send_session_config(self, session_info, ws: WebSocket):
        config = conf
        config.this_colour = session_info['colour'].value
        config.token = session_info['token']
        config.id = session_info['id']
        data = json.dumps(config.__dict__)
        data = bytearray(data, 'ascii')
        await self.send(Opcode.SESSION, data, ws)

    async def connect(self, ws: WebSocket, session_info):
        for i, token in enumerate(self.tokens):
            if token is None or token == session_info['token']:
                self.tokens[i] = session_info['token']
                break
            # else if theres no avaiable space for a new token
            if token == self.tokens[-1]:
                print("Failed to join session, token not found")
                await ws.close()
                return

        for i in self.ws:
            if self.ws[i] is None:
                self.ws[i] = ws
                session_info['colour'] = i
                self.counter += 1
                break

        await self.send_session_config(ws=ws, session_info=session_info)
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
        await self.send(Opcode.BOARD, data, ws)

    async def update_board(self, move: Move_Update, ws: WebSocket):
        colour = self.turn
        print(f"[{self.id}] - Current turn: {self.turn}")
        if self.counter != 2 or ws != self.ws[colour]:
            print(f"[{self.id}] - Denied update! connections: {self.counter}, \
            sent: {ws}, expected: {self.ws[colour]}")
            return

        move.state = colour
        self.board.put(move)
        removed_poses = self.board.get_encircled_positions(colour)
        move.removed_poses = removed_poses

        print(f"[{self.id}] - Updated: {self.turn} at {(move.x, move.y)}")
        await self.broadcast(Opcode.UPDATE, move.to_bytes())
        self.turn = self.turn.next_turn()

    async def send(self, req: Opcode, bytes, ws: WebSocket):
        data = [req.to_byte(), *bytes]
        data = struct.pack('!{}b'.format(len(data)), *data)
        await ws.send_bytes(data)

    async def broadcast(self, req: Opcode, bytes):
        for it in self.ws:
            if self.ws[it] is None:
                continue
            await self.send(req, bytes, self.ws[it])


class ConnectionManager:
    def __init__(self):
        self.sessions: dict[int, Session] = {}
        self.ws_to_session: dict[WebSocket, int] = {}

    def add_session(self, ws: WebSocket, id=None, session=None):
        # add a way to join a game with 1 player
        if id is None:
            if self.sessions:
                keys = list(self.sessions.keys())
                id = keys[-1] + 1
            else:
                id = 1
            session = Session(id)
            self.sessions[id] = session
        elif id in self.sessions:
            session = self.sessions[id]
        else:
            session = Session(id)
            self.sessions[id] = session
        self.ws_to_session[ws] = id
        return (id, session)

    async def run(self, ws: WebSocket):
        session = None
        while True:
            data = await ws.receive_bytes()
            request = Opcode(data[0])
            data = data[1:]

            if (not session and request == Opcode.SESSION):
                json_data = data.decode('utf-8')
                vars = json.loads(json_data)
                session_id = vars['id']
                if vars['token'] is None:
                    vars['token'] = secrets.token_hex(16)

                (session_id, session) = self.add_session(ws=ws, id=session_id)
                vars['id'] = session_id
                print(f"[{session_id}] - NEW SESSION CREATED")
                await session.connect(ws=ws, session_info=vars)

            if (session and request == Opcode.UPDATE):
                print(f"[{session_id}] - RECEIVED {request}")
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
        session_id = self.ws_to_session.pop(ws)
        session = self.sessions[session_id]
        session.disconnect(ws)
        if session.is_active() is False:
            self.sessions.pop(session_id)
        print(f"[{session_id}] - Disconnected {ws}")


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

#!/bin/python3

import struct
import json
import uvicorn
from copy import deepcopy
import secrets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from utils import State, Move_Update, Opcode, Config


global conf


# entry point
def main():
    global app
    global conf

    app = FastAPI()
    app.mount("/static", StaticFiles(directory="."), name="static")

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

    uvicorn.run(app, host='0.0.0.0', port=8000)


class Board:
    def __init__(self):
        self.data = [State.EMPTY] * (conf.map_dimensions * conf.map_dimensions)
        self.groups = {State.WHITE: [], State.BLACK: []}
        self.score = {State.WHITE: 0, State.BLACK: 0}
        self.previous_groups = None

    def iter(self, x: int, y: int):
        if not (0 <= x < conf.map_dimensions and 0 <= y < conf.map_dimensions):
            return None
        return x + y * (conf.map_dimensions)

    # returns a dictionary containing position entries for the colours
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

    # inserts a new position in the groups of stones
    # merges them if neccessary
    def merge_groups(self, new_pos: (int, int), state: State):
        self.previous_groups = deepcopy(self.groups)
        neighbours = self.get_neighbours(new_pos[0], new_pos[1])
        merge_idxs = []
        # find groups to which the neighbours belong to and try to join them
        # we don't want any duplicates in our set of positions
        merge_group = set()
        for pos in neighbours[state]:
            for i, _ in enumerate(self.groups[state]):
                if pos in self.groups[state][i]:
                    merge_idxs.append(i)
                    merge_group.update(self.groups[state][i])
        self.groups[state] = [self.groups[
            state][i] for i, _ in enumerate(self.groups[state])
            if i not in merge_idxs]
        merge_group.add(new_pos)
        self.groups[state].append(merge_group)

    # removes each group from the group_idcs list and returning removed poses
    def remove_group(self, group_idcs: int, state: State):
        removed_poses = []
        # iterating over reverse list -- TODO: DANGEROUS --
        for idx in reversed(group_idcs):
            poses = self.groups[state].pop(idx)
            for pos in poses:
                iter = self.iter(pos[0], pos[1])

                self.data[iter] = State.EMPTY
                removed_poses.append(pos)
        self.score[state.next_turn()] += len(removed_poses)
        return removed_poses if len(removed_poses) > 0 else None

    # returns number of encircled stones and indices of encircled groups
    def get_encircled_groups(self, state: State):
        # enemys colour
        encircled_groups = []
        gained_points = 0
        for i, group in enumerate(self.groups[state]):
            empty_spaces = 0
            points = 0

            # checks if any of the groups of the colour lack an empty space
            for pos in group:
                neighbours = self.get_neighbours(pos[0], pos[1])
                empty_spaces += len(neighbours[State.EMPTY])
                points += 1

            # found an encircled group of stones
            if empty_spaces == 0:
                encircled_groups.append(i)
                gained_points += points
        # returns gained points and indices pointing at encircled groups
        return (gained_points, encircled_groups)

    # puts the stone on the board
    def put(self, m: Move_Update):
        self.merge_groups((m.x, m.y), m.state)
        self.data[self.iter(m.x, m.y)] = m.state

    # reverts the previous move
    def revert_move(self, m: Move_Update):
        self.groups = deepcopy(self.previous_groups)
        self.data[self.iter(m.x, m.y)] = State.EMPTY

    # converts an array of States(ints) into an array of single bytes
    def to_array(self):
        return [i.to_byte() for i in self.data]


class Session:
    def __init__(self, id: int):
        self.counter = 0
        self.board = Board()
        self.tokens = [None] * 2
        self.turn = State.BLACK
        self.ws = {State.WHITE: None, State.BLACK: None}
        self.id = id
        self.is_ending = False

    async def send_session_config(self, session_info, ws: WebSocket):
        config = conf
        config.this_colour = session_info['colour'].value
        config.token = session_info['token']
        config.id = session_info['id']
        config.curr_turn = self.turn.value
        config.black_score = self.board.score[State.BLACK]
        config.white_score = self.board.score[State.WHITE]
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

    async def pass_turn(self, ws: WebSocket):
        if self.counter != 2 or ws != self.ws[self.turn]:
            return True

        print(f"[{self.id}] - Passed the move")

        if self.is_ending is True:
            self.turn = self.turn.next_turn()
            await self.broadcast(Opcode.FIN, [])
            self.tokens = [-1, -1]
            return False

        self.is_ending = True
        self.turn = self.turn.next_turn()
        await self.broadcast(Opcode.PASS, [])
        return True

    async def update_board(self, move: Move_Update, ws: WebSocket):
        colour = self.turn
        if self.counter != 2 or ws != self.ws[colour]:
            print(f"[{self.id}] - Denied update! connections: {self.counter}, \
            sent: {ws}, expected: {self.ws[colour]}")
            return

        self.is_ending = False
        move.state = colour
        self.board.put(move)
        enemy_colour = move.state.next_turn()

        # points gain for the placement (to be captured by the turnmaker)
        (gained_pts, rmv_indices) = \
            self.board.get_encircled_groups(enemy_colour)

        # points loss for the placement (to be captured by the enemy)
        (lost_pts, _) = self.board.get_encircled_groups(colour)

        # the move is illegal when the turnmaker looses more than he would gain
        if lost_pts != 0 and gained_pts <= lost_pts:
            self.board.revert_move(move)
            print(f"gain: {gained_pts}, lost {lost_pts}")
            print(f"[{self.id}] - Reverted: {self.turn} at {(move.x, move.y)}")
            rmv_indices = None
            return

        # else
        rmv_poses = self.board.remove_group(rmv_indices, enemy_colour)
        move.removed_poses = rmv_poses
        print(f"[{self.id}] - Updated: {self.turn} at {(move.x, move.y)}")
        await self.broadcast(Opcode.UPDATE, move.to_bytes())
        self.turn = self.turn.next_turn()
        print(f"[{self.id}] - Current turn: {self.turn}")

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
        is_running = True
        while is_running:
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

            if (session and request == Opcode.PASS):
                is_running = await session.pass_turn(ws)
                if is_running is False:
                    self.disconnect(ws)

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


if __name__ == "__main__":
    main()

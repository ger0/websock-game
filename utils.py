from enum import Enum


class State(Enum):
    EMPTY = 0
    WHITE = 1
    BLACK = 2

    def to_byte(self):
        return self.value.to_bytes(1)[0]

    def next_turn(self):
        if self == State.BLACK:
            self = State.WHITE
        elif self == State.WHITE:
            self = State.BLACK
        return self


class Opcode(Enum):
    SESSION = 0
    CONFIG = 1
    BOARD = 2
    UPDATE = 3
    REMOVE = 4

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


# default values
class Config:
    map_dimensions = 8
    circle_colours = ['red', 'black']
    circle_size = 35

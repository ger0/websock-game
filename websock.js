var address = window.location.hostname + (window.location.port ? ":" + window.location.port : "");
// Get the parameter value from the URL
const urlParams = new URLSearchParams(window.location.search);

let session = {
    id              : urlParams.get('id'),
    token           : localStorage.getItem('token')
}

if (session.id === null) {
    const session_id = localStorage.getItem('session_id');
    if (session_id != null) {
        session.id = session_id;
    } else {
        session.id = null
    }
} else {
    console.log("Session id from parameter: ", session.id);
}

if (session.token === null) {
    session.token = null
} else {
    console.log("Token from storage: ", session.token);
}

// Create a new WebSocket connection
const socket = new WebSocket(`ws://${address}/ws`);

const Value = {
    EMPTY : 0,
    WHITE : 1,
    BLACK : 2
}

let player_scores = {
    WHITE: 0,
    BLACK: 0
}

let current_turn = Value.WHITE;

var session_config = {
    map_dimensions  : 19,
    colours         : ['white', 'black'],
    circle_size     : 40,
    this_colour     : Value.WHITE,
    token           : null
}


next_turn = function(current) {
    if (current == Value.WHITE) { 
        return Value.BLACK; 
    } else if (current == Value.BLACK) { 
        return Value.WHITE; 
    }
}

const Opcode = {
    SESSION : 0,
    CONFIG  : 1,
    BOARD   : 2,
    UPDATE  : 3
}

// sending game updates to the server
document.addEventListener('DOMContentLoaded', function() {
    const canvas = document.getElementById('canvas');

    // Try to send an update
    canvas.addEventListener('click', (event) => {
        const rect = canvas.getBoundingClientRect();
        const clickX = event.clientX - rect.left;
        const clickY = event.clientY - rect.top;

        // Calculate the grid cell indices based on click coordinates
        const x = Math.floor(clickX / session_config.circle_size);
        const y = Math.floor(clickY / session_config.circle_size);

        // check if theres an object on the board already
        if (board.at(x, y) != Value.EMPTY || session_config.this_colour != current_turn) {
            return;
        }

        // data to be sent
        const data = new Array(2);
        [data[0], data[1]] = [x, y];
        send(Opcode.UPDATE, data);
    });

    const pass_button = document.getElementById('passButton');

    // pass the turn
    pass_button.addEventListener('click', function() {
        if (session_config.this_colour != current_turn) {
            return;
        }
        const data = new Array(2);
        [data[0], data[1]] = [
            session_config.map_dimensions, 
            session_config.map_dimensions
        ];
        send(Opcode.UPDATE, data);
    });
});

send = function(opcode, array) {
    const data = new Uint8Array([opcode].concat(Array.from(array)));
    socket.send(data);
}

load_configuration = function(data) {
    const json = JSON.parse(String.fromCharCode(...data));

    session_config.map_dimensions  = json.map_dimensions;
    session_config.colours         = json.circle_colours;
    session_config.circle_size     = json.circle_size;
    session_config.this_colour     = json.this_colour;
    session.token                  = json.token;
    session.id                     = json.id;
    localStorage.setItem('token', session.token);
    localStorage.setItem('session_id', session.id);

    console.log("This colour: ", session_config.this_colour);
    console.log("Token: ", session.token);
    console.log("Session ID: ", session.id);

    canvas.width    = session_config.map_dimensions * session_config.circle_size;
    canvas.height   = session_config.map_dimensions * session_config.circle_size;
}

// When the connection is open
socket.onopen = function(_event) {
    var session_str = JSON.stringify(session);
    var encoder = new TextEncoder();
    const binary_data = encoder.encode(session_str);
    send(Opcode.SESSION, binary_data);
    console.log('WebSocket connection established.');
};

let board = {
    _arr: new Uint8Array(session_config.map_dimensions * session_config.map_dimensions),
    _iter: function(x, y) {
        return x + session_config.map_dimensions * y;
    },
    get: function() {
        return this._arr;
    },
    set: function(x, y, value) {
        this._arr[this._iter(x, y)] = value;
    },
    at: function(x, y) {
        return this._arr[this._iter(x, y)];
    },
    load: function(data) {
        this._arr = data;
    }
};

handle_request = function(opcode, data) {
    switch(opcode) {
        case Opcode.SESSION:
            console.log("Received Game Config");
            load_configuration(data);
            break;
            
        case Opcode.BOARD:
            console.log("Received Game State");
            board.load(data);
            draw_board(board);
            break;

        case Opcode.UPDATE:
            console.log("Received Game Update");
            let [val, x, y] = [data[0], data[1], data[2]];
            if (val == Value.EMPTY) {
                current_turn = next_turn(current_turn);
                console.log("Recieved Passed Turn");
                draw_board(board);
                break;
            }
            let index = 0;
            board.set(x, y, val);
            console.log(`x: ${x}, y: ${y}, value: ${val}`);
            
            // remove stones
            let add_score = 0;
            index += 3;
            while (index < data.length) {
                [x, y] = [data[index], data[index + 1]];
                board.set(x, y, Value.EMPTY);
                index += 2;
                add_score += 1;
                console.log(`x: ${x}, y: ${y}, erased`);
            }
            if (val == Value.WHITE) {
                player_scores.WHITE += add_score;
            } else if (val == Value.BLACK) {
                player_scores.BLACK += add_score;
            }
            current_turn = next_turn(val);
            draw_board(board);
            break;
    }
}

// When a message is received
socket.onmessage = function(event) {
    // Get the text message from the event
    const reader  = new FileReader();
    reader.addEventListener("loadend", function() {
        let data = new Uint8Array(reader.result);
        const opcode = data[0];
        data = data.slice(1);

        handle_request(opcode, data);
    });
    reader.readAsArrayBuffer(event.data);
};

draw_grid = function() {
    const ctx = canvas.getContext('2d');
    const grid_radius = session_config.circle_size / 2

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    for (let x = grid_radius; x < canvas.width; x += grid_radius * 2) {
        ctx.moveTo(x, grid_radius);
        ctx.lineTo(x, canvas.height - grid_radius);
    }

    for (let y = grid_radius; y < canvas.height; y += grid_radius * 2) {
        ctx.moveTo(grid_radius, y);
        ctx.lineTo(canvas.width - grid_radius, y);
    }

    ctx.strokeStyle = 'black';
    ctx.lineWidth = 1;

    ctx.stroke();
}

draw_board = function(board) {
    draw_grid();
    const radius = session_config.circle_size / 2;
    const dimensions = session_config.map_dimensions;
    const colours = session_config.colours;
    const spacing = 2;
    const turn_text = document.getElementById('turnIndicator');
    turn_text.textContent = current_turn == Value.WHITE ? "WHITE" : "BLACK";

    const white_points = document.getElementById('white_points');
    const black_points = document.getElementById('black_points');
    white_points.textContent = player_scores.WHITE;
    black_points.textContent = player_scores.BLACK;

    const array = board.get();

    const ctx = canvas.getContext('2d');

    // Draw the grid of circles
    for (let row = 0; row < dimensions; row++) {
        for (let col = 0; col < dimensions; col++) {
            const value = array[col + row * dimensions];
            if (value == Value.EMPTY) continue;
            const x = col * radius * 2 + radius;
            const y = row * radius * 2 + radius;

            // Draw a circle
            ctx.beginPath();
            ctx.arc(x, y, radius - spacing, 0, 2 * Math.PI);
            ctx.fillStyle = (value == Value.BLACK) ? colours[1] : colours[0];
            ctx.fill();
            ctx.closePath();
        }
    }
}

// When the connection is closed
socket.onclose = function(_event) {
    console.log('WebSocket connection closed.');
};

// Create a new WebSocket connection
const socket = new WebSocket('ws://localhost:8000/ws');

const Value = {
    EMPTY : 0,
    WHITE : 1,
    BLACK : 2
}

const Opcodes = {
    CONFIGURE_GAME    : 0,
    UPDATE_BOARD      : 1,
    LOAD_WHOLE_BOARD  : 2
}

const config = {
    map_dimensions : 19,
    colours : ['white', 'black'],
    circle_size : 40
}

const canvas = document.getElementById('canvas');

// Mouse click event listener
canvas.addEventListener('click', (event) => {
    const rect = canvas.getBoundingClientRect();
    const clickX = event.clientX - rect.left;
    const clickY = event.clientY - rect.top;

    // Calculate the grid cell indices based on click coordinates
    const x = Math.floor(clickX / config.circle_size);
    const y = Math.floor(clickY / config.circle_size);

    // data to be sent
    const data = new Array(2);
    [data[0], data[1]] = [x, y];
    send(Opcodes.UPDATE_BOARD, data);
});

send = function(opcode, array) {
    const data = new Uint8Array([opcode].concat(array));
    socket.send(data);
}

load_configuration = function(data) {
    const json = JSON.parse(String.fromCharCode(...data));

    config.map_dimensions  = json.map_dimensions;
    config.colours         = json.circle_colours;
    config.circle_size     = json.circle_size;

    console.log("Map Dimensions: ", config.map_dimensions);
    console.log("Circle Colours: ", config.colours);
    console.log("Circle Size: ",    config.circle_size);

    canvas.width = config.map_dimensions * config.circle_size;
    canvas.height = config.map_dimensions * config.circle_size;
}

// When the connection is open
socket.onopen = function(_event) {
    console.log('WebSocket connection established.');
};

let board = {
    _arr: new Uint8Array(config.map_dimensions * config.map_dimensions),
    _iter: function(x, y) {
        return x + config.map_dimensions * y;
    },
    get: function() {
        return this._arr;
    },
    set: function(x, y, value) {
        this._arr[this._iter(x, y)] = value;
    },
    load: function(data) {
        this._arr = data;
    }
};

handle_request = function(opcode, data) {
    switch(opcode) {
        case Opcodes.CONFIGURE_GAME:
            console.log("Received Game Config");
            load_configuration(data);
            break;
            
        case Opcodes.LOAD_WHOLE_BOARD:
            console.log("Received Game State");
            board.load(data);
            draw_board(board);
            break;

        case Opcodes.UPDATE_BOARD:
            console.log("Received Game Update");
            const [x, y, val] = [data[0], data[1], data[2]];
            board.set(x, y, val);
            console.log(`x: ${x}, y: ${y}, value: ${val}`);

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
    const grid_radius = config.circle_size / 2

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
    const radius = config.circle_size / 2;
    const dimensions = config.map_dimensions;
    const colours = config.colours;
    const spacing = 2;

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

// entry point????
{
    // 
}

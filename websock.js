// Create a new WebSocket connection
const socket = new WebSocket('ws://localhost:8000/ws');

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

    console.log(`Clicked on cell (${x}, ${y})`);
});

send = function(opcode, bytes) {
    const data = new Uint8Array(opcode, bytes);
    socket.send(data);
}

load_configuration = function(data) {
    const json = JSON.parse(String.fromCharCode(...data));

    config.map_dimensions  = json.map_dimensions;
    config.colours         = json.circle_colours;
    config.circle_size     = json.circle_size;

    console.log("LOADING CONFIGURATION");
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

handle_request = function(opcode, data) {
    switch(opcode) {
        case Opcodes.CONFIGURE_GAME:
            load_configuration(data);
            break;
            
        case Opcodes.LOAD_WHOLE_BOARD:
            draw_grid();
            draw_board(data);
            break;

        case Opcodes.UPDATE_BOARD:
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

        console.log("received request: ", opcode);
        handle_request(opcode, data);
    });
    reader.readAsArrayBuffer(event.data);
};

draw_grid = function() {
    const ctx = canvas.getContext('2d');
    for (let x = config.circle_size / 2; x < canvas.width; x += config.circle_size) {
        ctx.moveTo(x, 0);
        ctx.lineTo(x, canvas.height);
    }

    for (let y = config.circle_size / 2; y < canvas.height; y += config.circle_size) {
        ctx.moveTo(0, y);
        ctx.lineTo(canvas.width, y);
    }

    ctx.strokeStyle = 'black';
    ctx.lineWidth = 1;

    ctx.stroke();
}

draw_board = function(board) {
    const radius = config.circle_size / 2;
    const dimensions = config.map_dimensions;
    const colours = config.colours;

    const ctx = canvas.getContext('2d');

    // Draw the grid of circles
    for (let row = 0; row < dimensions; row++) {
        for (let col = 0; col < dimensions; col++) {
            const value = board[col + row * dimensions];
            if (value == 0) continue;
            const x = col * radius * 2 + radius;
            const y = row * radius * 2 + radius;

            // Draw a circle
            ctx.beginPath();
            ctx.arc(x, y, radius, 0, 2 * Math.PI);
            ctx.fillStyle = (value == 1) ? colours[1] : colours[0];
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

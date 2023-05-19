// Create a new WebSocket connection
const socket = new WebSocket('ws://localhost:8000/ws');

const Opcodes = {
    CONFIGURE_GAME    : 0,
    UPDATE_BOARD      : 1,
    LOAD_WHOLE_BOARD  : 2
}

let map_dimensions = 8;
let colours = ['white', 'black'];
let circle_size = 40;

load_configuration = function(data) {
    const json = JSON.parse(String.fromCharCode(...data));

    console.log(json);
    map_dimensions  = json.map_dimensions;
    colours         = json.circle_colours;
    circle_size     = json.circle_size;

    console.log("LOADING CONFIGURATION");
    console.log("Map Dimensions: ", map_dimensions);
    console.log("Circle Colours: ", colours);
    console.log("Circle Size: ", circle_size);
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
            draw_board(data)
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

draw_board = function(board) {
    // var dimension = [document.documentElement.clientWidth, document.documentElement.clientHeight];
    const circleRadius = 40;
    const circleSpacing = 2;

    canvas.width    = 16 * (circleRadius + 1/2 * circleSpacing);
    canvas.height   = 16 * (circleRadius + 1/2 * circleSpacing);

    const ctx = canvas.getContext('2d');

    // const gridWidth = canvas.width / (circleRadius * 2 + circleSpacing);
    // const gridHeight = canvas.height / (circleRadius * 2 + circleSpacing);

    // Draw the grid of circles
    for (let col = 0; col < map_dimensions; col++) {
        for (let row = 0; row < map_dimensions; row++) {
            const value = board[row + col * map_dimensions];
            if (value == 0) continue;
            const x = col * (circleRadius * 2 + circleSpacing) + circleRadius;
            const y = row * (circleRadius * 2 + circleSpacing) + circleRadius;

            // Draw a circle
            ctx.beginPath();
            ctx.arc(x, y, circleRadius, 0, 2 * Math.PI);
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

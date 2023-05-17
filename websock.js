// Create a new WebSocket connection
const socket = new WebSocket('ws://localhost:8000/ws');

var map_dimensions = 0;
var colours = ['white', 'black'];

load_configuration = function(filename) {
    fetch(filename)
        .then(response => response.json())
        .then(data => {
            map_dimensions = data.map_dimensions;
            colours = data.colours;

            console.log("LOADING CONFIGURATION FROM ", filename);
            console.log("Map dimensions: ", map_dimensions);
            console.log("Colours: ", colours);
        })
        .catch(error => {
            console.error('Error while loading configuration:', error);
        });
}

// When the connection is open
socket.onopen = function(event) {
    console.log('WebSocket connection established.');
};

// When a message is received
socket.onmessage = function(event) {
    // Get the text message from the event
    const reader  = new FileReader();
    reader.addEventListener("loadend", function() {
        const data = new Uint8Array(reader.result);

        const dimensions = data.slice(0, 1)[0];
        const board = data.slice(1);

        console.log("Dimensions: ", dimensions);
        console.log(board);
        draw_board(dimensions, board);
    });
    reader.readAsArrayBuffer(event.data);
};

draw_board = function(dim, board) {
    // var dimension = [document.documentElement.clientWidth, document.documentElement.clientHeight];
    const circleRadius = 50;
    const circleSpacing = 2;

    canvas.width    = 16 * (circleRadius + 1/2 * circleSpacing);
    canvas.height   = 16 * (circleRadius + 1/2 * circleSpacing);

    const ctx = canvas.getContext('2d');

    const gridWidth = canvas.width / (circleRadius * 2 + circleSpacing);
    const gridHeight = canvas.height / (circleRadius * 2 + circleSpacing);

    // Draw the grid of circles
    for (let row = 0; row < dim; row++) {
        for (let col = 0; col < dim; col++) {
            const x = col * (circleRadius * 2 + circleSpacing) + circleRadius;
            const y = row * (circleRadius * 2 + circleSpacing) + circleRadius;

            // Draw a circle
            ctx.beginPath();
            ctx.arc(x, y, circleRadius, 0, 2 * Math.PI);
            ctx.fillStyle = 'black';
            ctx.fill();
            ctx.closePath();
        }
    }
}

// When the connection is closed
socket.onclose = function(event) {
    console.log('WebSocket connection closed.');
};


// entry point????
{
    load_configuration("config.json");
}

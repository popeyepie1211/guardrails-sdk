// test/mock-server.js
import http from 'http';

const PORT = 3000;

// This server acts as the "Guardrail Backend"
const server = http.createServer((req, res) => {
  // We only care about POST requests to /v1/ingest
  if (req.method === 'POST' && req.url === '/v1/ingest') {
    let body = '';

    // Listen for data chunks coming from your SDK
    req.on('data', chunk => {
      body += chunk.toString();
    });

    // Once the whole batch is received
    req.on('end', () => {
      const data = JSON.parse(body);
      console.log("\n📩 [Mock Server] RECEIVED A NEW BATCH!");
      console.log(`📦 Batch ID: ${data.batchId}`);
      console.log(`📊 Items in Batch: ${data.payload.length}`);
      
      // Look at the first item to verify the data structure
      const firstItem = data.payload[0];
      console.log("🔍 Sample Data Point:", {
        model: firstItem.modelId,
        input: firstItem.input,
        output: firstItem.output,
        latency: firstItem.latency + "ms"
      });

      // Send a "Success" response back to the SDK's Transport layer
      res.writeHead(201, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'success', message: 'Vitals recorded' }));
    });
  } else {
    res.writeHead(404);
    res.end();
  }
});

server.listen(PORT, () => {
  console.log(`📡 Mock Server is running at http://localhost:${PORT}`);
  console.log("Waiting for SDK batches...\n");
});


// ye woh mock
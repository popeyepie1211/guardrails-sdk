// test/mock-server.js
import express from 'express';
import { createClient } from 'redis';

const app = express();
const PORT = 3000;

// 1. INITIALIZE REDIS CLIENT
const redisClient = createClient({
    url: 'redis://localhost:6379' 
});

redisClient.on('error', (err) => console.error('❌ Redis Error:', err));

// Connect to Redis before starting the server
await redisClient.connect();
console.log("🚀 Connected to Redis Shock Absorber");

// Middleware to handle JSON payloads from your SDK
app.use(express.json());

/**
 * THE INGESTION ENDPOINT
 * This is where your SDK's Transport layer sends the data
 */
app.post('/v1/ingest', async (req, res) => {
    try {
        const batch = req.body; // This is the payload from transport.js

        // 2. THE BURST MANAGEMENT (LPUSH)
        // We "park" the entire batch into a Redis list called 'vitals_queue'
        // This takes microseconds because it's writing to RAM
        await redisClient.lPush('vitals_queue', JSON.stringify(batch));

        console.log(`📩 [API] Batch ${batch.batchId} queued in Redis. Items: ${batch.payload.length}`);

        // 3. INSTANT ACKNOWLEDGMENT
        // We tell the SDK "Success" immediately so it can get back to the AI model
        res.status(201).json({ 
            status: 'success', 
            message: 'Batch queued for auditing' 
        });

    } catch (error) {
        console.error('❌ Ingestion Error:', error);
        res.status(500).json({ status: 'error', message: 'Internal server error' });
    }
});

app.listen(PORT, () => {
    console.log(`📡 Ingestion API live at http://localhost:${PORT}`);
    console.log("Waiting for SDK bursts...\n");
});
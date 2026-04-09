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

await redisClient.connect();
console.log("🚀 Connected to Redis Shock Absorber");


app.use(express.json());


app.post('/v1/ingest', async (req, res) => {
    try {
        const batch = req.body; // This is the payload from transport.js

        
        await redisClient.lPush('vitals_queue', JSON.stringify(batch));

        console.log(`📩 [API] Batch ${batch.batchId} queued in Redis. Items: ${batch.payload.length}`);
    
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
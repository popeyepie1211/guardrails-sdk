/**
 * ingestion-server.js
 * 
 * Permanent, always-on ingestion endpoint for Guardrail AI.
 * Receives SDK batches and queues them in Redis for worker consumption.
 * 
 * Usage:
 *   node ingestion-server.js
 * 
 * Listens on http://localhost:3000
 * Health check: GET /health
 * Ingestion: POST /v1/ingest
 */

import express from 'express';
import { createClient } from 'redis';
import { v4 as uuidv4 } from 'uuid';

const app = express();
const PORT = process.env.PORT || 3000;
const REDIS_URL = process.env.REDIS_URL || 'redis://localhost:6379';
const VITALS_QUEUE = 'vitals_queue';

// ============================================
// REDIS CLIENT SETUP
// ============================================
const redisClient = createClient({
    url: REDIS_URL,
    socket: {
        reconnectStrategy: (retries) => {
            const delay = Math.min(retries * 50, 500);
            return delay;
        }
    }
});

redisClient.on('error', (err) => {
    console.error('❌ [Redis] Connection Error:', err.message);
    process.exit(1);
});

redisClient.on('connect', () => {
    console.log('✅ [Redis] Connected to shock absorber');
});

await redisClient.connect();

// ============================================
// EXPRESS MIDDLEWARE
// ============================================
app.use(express.json({ limit: '10mb' }));

// ============================================
// HEALTH CHECK ENDPOINT
// ============================================
app.get('/health', async (req, res) => {
    try {
        // Verify Redis connectivity
        await redisClient.ping();
        
        // Get queue depth for monitoring
        const queueDepth = await redisClient.lLen(VITALS_QUEUE);
        
        res.status(200).json({
            status: 'healthy',
            timestamp: new Date().toISOString(),
            redis: 'connected',
            queueDepth,
            uptime: process.uptime()
        });
    } catch (error) {
        res.status(503).json({
            status: 'unhealthy',
            timestamp: new Date().toISOString(),
            redis: 'disconnected',
            error: error.message
        });
    }
});

// ============================================
// INGESTION ENDPOINT
// ============================================
app.post('/v1/ingest', async (req, res) => {
    try {
        const batch = req.body;

       
        if (!batch.batchId || !batch.modelId || !Array.isArray(batch.payload)) {
            return res.status(400).json({
                status: 'error',
                message: 'Invalid batch: missing batchId, modelId, or payload array'
            });
        }

        if (batch.payload.length === 0) {
            return res.status(400).json({
                status: 'error',
                message: 'Empty payload'
            });
        }

        // Push to Redis queue
        const queueKey = `${VITALS_QUEUE}:${batch.modelId}`;
        await redisClient.lPush(queueKey, JSON.stringify(batch));

        // Also push to unified queue for multi-model workers
        await redisClient.lPush(VITALS_QUEUE, JSON.stringify({
            ...batch,
            enqueuedAt: new Date().toISOString()
        }));

        console.log(`📩 [Ingest] Batch ${batch.batchId} (Model: ${batch.modelId}) queued. Items: ${batch.payload.length}`);

        res.status(201).json({
            status: 'success',
            message: 'Batch queued for auditing',
            batchId: batch.batchId,
            itemCount: batch.payload.length,
            enqueuedAt: new Date().toISOString()
        });

    } catch (error) {
        console.error('❌ [Ingest] Error:', error.message);
        res.status(500).json({
            status: 'error',
            message: 'Internal server error',
            error: process.env.NODE_ENV === 'development' ? error.message : undefined
        });
    }
});

// ============================================
// STATS ENDPOINT (for monitoring)
// ============================================
app.get('/stats', async (req, res) => {
    try {
        const queueDepth = await redisClient.lLen(VITALS_QUEUE);
        
        res.status(200).json({
            timestamp: new Date().toISOString(),
            queue: {
                name: VITALS_QUEUE,
                depth: queueDepth
            }
        });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// ============================================
// GRACEFUL SHUTDOWN
// ============================================
process.on('SIGTERM', async () => {
    console.log('\n⏹️  [Ingestion] SIGTERM received. Shutting down gracefully...');
    await redisClient.quit();
    process.exit(0);
});

process.on('SIGINT', async () => {
    console.log('\n⏹️  [Ingestion] SIGINT received. Shutting down gracefully...');
    await redisClient.quit();
    process.exit(0);
});

// ============================================
// START SERVER
// ============================================
app.listen(PORT, () => {
    console.log(`🚀 [Ingestion Server] Live at http://localhost:${PORT}`);
    console.log(`📡 POST /v1/ingest - SDK batch ingestion`);
    console.log(`💚 GET  /health - Health check`);
    console.log(`📊 GET  /stats - Queue statistics`);
    console.log(`\n⏳ Waiting for SDK bursts...\n`);
});

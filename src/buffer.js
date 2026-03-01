// src/buffer.js

export class DataBuffer {
  /**
   * @param {Function} onFlush - The function (from Transport) to call when sending data
   */
  constructor(onFlush) {
    this.queue = [];
    this.onFlush = onFlush;
    
    // CONFIGURATION (Adjust these for the 1-lakh user scale)
    this.maxBatchSize = 50;      // Send after 50 predictions
    this.flushInterval = 5000;   // Or every 5 seconds (whichever comes first)
    this.maxQueueLimit = 5000;   // Safety: Drop data if we have 5k unsent items
    
    // Start the "Heartbeat" timer
    this.timer = setInterval(() => this.flush(), this.flushInterval);
  }

  /**
   * Pushes new prediction data into the queue
   */
  push(data) {
    // Safety Check: If the buffer is overflowing (backend down?), drop the oldest
    if (this.queue.length >= this.maxQueueLimit) {
      console.warn("⚠️ [Guardrail SDK] Buffer Limit Reached. Dropping oldest data point.");
      this.queue.shift(); 
    }

    this.queue.push(data);

    // If we hit the batch size, flush immediately without waiting for the timer
    if (this.queue.length >= this.maxBatchSize) {
      this.flush();
    }
  }

  /**
   * Clears the queue and sends it to the Transport layer
   */
  async flush() {
    if (this.queue.length === 0) return;

    // 1. Snapshot the current queue and clear it immediately
    const batchToSend = [...this.queue];
    this.queue = []; 

    // 2. Hand off to the Transport layer (Non-blocking)
    try {
      await this.onFlush(batchToSend);
    } catch (err) {
      console.error("❌ [Guardrail SDK] Flush failed. Data lost for this batch.");
      // Note: In a future version, we could re-insert this into the queue for retry
    }
  }
}
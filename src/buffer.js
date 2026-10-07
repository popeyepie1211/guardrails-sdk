// src/buffer.js
import { DEFAULT_BATCH_SIZE, DEFAULT_FLUSH_INTERVAL_MS, DEFAULT_MAX_QUEUE_LIMIT } from './constants.js';

export class DataBuffer {
  /**
   * @param {Function} onFlush - The function (from Transport) to call when sending data
   */
  constructor(onFlush, options = {}) {
    this.queue = [];
    this.onFlush = onFlush;
    this.pending = new Set();
    this.maxBatchSize = options.batchSize ?? DEFAULT_BATCH_SIZE;
    this.flushInterval = options.flushIntervalMs ?? DEFAULT_FLUSH_INTERVAL_MS;
    this.maxQueueLimit = options.maxQueueLimit ?? DEFAULT_MAX_QUEUE_LIMIT;

    this.timer = setInterval(() => this.flush(), this.flushInterval);
    this.timer.unref?.();
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
    if (this.queue.length === 0) return Promise.all(this.pending);

    const batchToSend = [...this.queue];
    this.queue = [];

    const delivery = Promise.resolve().then(() => this.onFlush(batchToSend))
      .catch(err => console.error('❌ [Guardrail SDK] Flush failed. Data lost for this batch.', err))
      .finally(() => this.pending.delete(delivery));
    this.pending.add(delivery);
    return delivery;
  }

  async shutdown() {
    clearInterval(this.timer);
    await this.flush();
    await Promise.all(this.pending);
  }
}

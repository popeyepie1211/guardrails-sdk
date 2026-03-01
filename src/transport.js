// src/transport.js
import axios from 'axios';

export class Transport {
  constructor(config) {
    this.apiKey = config.apiKey;
    this.modelId = config.modelId;
    this.endpoint = config.endpoint || 'https://api.guardrail.ai/v1/ingest';
    
    // Create an Axios instance with pre-configured headers
    this.api = axios.create({
      baseURL: this.endpoint,
      headers: {
        'Content-Type': 'application/json',
        'X-API-KEY': this.apiKey,
        'X-MODEL-ID': this.modelId,
        'X-SDK-VERSION': '1.0.0'
      },
      timeout: 5000 // If the server takes >5s, we move on (non-blocking)
    });
  }

  /**
   * Sends the batch to the backend
   */
  async sendBatch(batch) {
    try {
      const response = await this.api.post('', {    // POST to the base URL with the batch as the body
        batchId: Date.now().toString(36), // Simple unique ID for the batch
        payload: batch
      });
      
      if (response.status === 200 || response.status === 201) {
        console.log(`✅ [Transport] Successfully delivered batch of ${batch.length} items.`);
      }
    } catch (error) {
    
      console.error('❌ [Transport] Failed to send vitals batch:', error.message);
      
      // Future Enhancement: This is where we would trigger "Retry Logic"
      return false;
    }
  }
}
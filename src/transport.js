// src/transport.js
import axios from 'axios';
import { DEFAULT_MAX_RETRIES, DEFAULT_REQUEST_TIMEOUT_MS, SDK_VERSION } from './constants.js';

export class Transport {
  constructor(config) {
    this.apiKey = config.apiKey;
    this.modelId = config.modelId;
    this.endpoint = config.endpoint || 'https://api.guardrail.ai/v1/ingest';
    this.domain = config.domain || 'standard';
    this.predictionType = config.predictionType || 'binary';
    this.nodeName = config.nodeName || 'SDK_Intercept';
    this.modelVersion = config.modelVersion || 'latest';
    this.maxRetries = config.maxRetries ?? DEFAULT_MAX_RETRIES;
    this.onError = config.onError;
    
    // Create an Axios instance with pre-configured headers
    this.api = axios.create({
      baseURL: this.endpoint,
      headers: {
        'Content-Type': 'application/json',
        'X-API-KEY': this.apiKey,
        'X-MODEL-ID': this.modelId,
        'X-SDK-VERSION': SDK_VERSION
      },
      timeout: config.requestTimeoutMs ?? DEFAULT_REQUEST_TIMEOUT_MS
    });
  }

  /**
   * Sends the batch to the backend
   */
  async sendBatch(batch) {
    const envelope = {
      batchId: Date.now().toString(36),
      modelId: this.modelId,
      sdkVersion: SDK_VERSION,
      sentAt: new Date().toISOString(),
      metadata: {
        domain: this.domain,
        prediction_type: this.predictionType,
        node_name: this.nodeName,
        model_version: this.modelVersion
      },
      payload: batch
    };

    for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
      try {
        const response = await this.api.post('', envelope);
        if (response.status === 200 || response.status === 201) {
          console.log(`✅ [Transport] Successfully delivered batch of ${batch.length} items.`);
        }
        return true;
      } catch (error) {
        const status = error.response?.status;
        const context = { batchId: envelope.batchId, modelId: this.modelId };
        if (status === 401 || status === 403) {
          this.reportError(error, { ...context, type: 'auth' },
            `Invalid or missing API key for model ${this.modelId}; batch ${envelope.batchId} dropped (HTTP ${status}).`);
          return false;
        }
        if (status >= 400 && status < 500) {
          const body = JSON.stringify(error.response.data);
          this.reportError(error, { ...context, type: 'validation' },
            `Batch ${envelope.batchId} rejected for model ${this.modelId} (HTTP ${status}); response: ${body}. Data lost.`);
          return false;
        }
        if (attempt === this.maxRetries) {
          this.reportError(error, { ...context, type: 'network' },
            `Delivery failed after ${attempt + 1} attempts for model ${this.modelId}; batch ${envelope.batchId} data lost: ${error.message}`);
          return false;
        }
        await new Promise(resolve => setTimeout(resolve, 1000 * 2 ** attempt));
      }
    }
  }

  reportError(error, context, message) {
    console.error(`[Transport:${context.type}] ${message}`);
    if (typeof this.onError === 'function') {
      try {
        this.onError(error, context);
      } catch (callbackError) {
        console.error('[Transport] onError callback failed:', callbackError);
      }
    }
  }
}

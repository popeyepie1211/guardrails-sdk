// src/index.js
import { deepClone, getTimestamp } from './utils/helpers.js';
import { DataBuffer } from './buffer.js';

class Guardrail {
  constructor() {
    this.buffer = new DataBuffer(this.sendToBackend.bind(this));
    this.modelId = null;
  }

  init({ apiKey, modelId }) {
    this.apiKey = apiKey;
    this.modelId = modelId;
    console.log(`🛡️ [Guardrail] SDK Initialized for Model: ${modelId}`);
  }

  /**
   * The Interceptor Module
   * Wraps the model in a Proxy to trap the .predict() method
   */
  wrap(model) {
    const sdk = this;

    return new Proxy(model, {
      get(target, prop, receiver) { // Intercept property access
        const originalValue = Reflect.get(target, prop, receiver);  // Get the original property value

        // We only care about the 'predict' method
        if (typeof originalValue === 'function' && prop === 'predict') {
          return async function (...args) {
            const start = performance.now(); // High-res latency start
            
            let result;
            try {
              // 1. EXECUTE ORIGINAL MODEL (The user's core logic)
              result = await originalValue.apply(this, args);
            } catch (modelError) {
              // If the USER'S model fails, we let that error bubble up
              throw modelError;
            }

            // 2. CAPTURE DATA (The SDK Logic)
            // We wrap this in its own try-catch so the SDK NEVER crashes the app
            try {
              const latency = (performance.now() - start).toFixed(4);
              
              sdk.buffer.push({
                modelId: sdk.modelId,
                timestamp: getTimestamp(),
                latency: parseFloat(latency),
                input: deepClone(args[0]), // Captured Features
                output: deepClone(result)   // Captured Prediction
              });
            } catch (sdkError) {
              console.warn("⚠️ [Guardrail SDK] Failed to capture vitals, but prediction continued.", sdkError);
            }

            return result;
          };
        }

        return originalValue;
      }
    });
  }

  async sendToBackend(batch) {
    // This is where transport.js will take over tomorrow
    console.log(`📦 [Batch Dispatch] Sending ${batch.length} items to infrastructure.`);
  }
}

export default new Guardrail();
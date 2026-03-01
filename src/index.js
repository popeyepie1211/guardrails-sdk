
import { deepClone, getTimestamp } from './utils/helpers.js';
import { DataBuffer } from './buffer.js';
import { Transport } from './transport.js'; 

class Guardrail {
  constructor() {
    this.buffer = null;    
    this.transport = null; 
    this.modelId = null;
    this.apiKey = null;
  }

 
  init({ apiKey, modelId, endpoint }) {
    this.apiKey = apiKey;
    this.modelId = modelId;

  
    this.transport = new Transport({ apiKey, modelId, endpoint });

    
    this.buffer = new DataBuffer((batch) => this.transport.sendBatch(batch));

    console.log(`🛡️ [Guardrail] SDK Initialized for Model: ${modelId}`);
  }

  
  wrap(model) {
    const sdk = this;

  
    if (!sdk.buffer) {
      console.warn("⚠️ [Guardrail] SDK wrap() called before init(). Data will not be captured.");
      return model;
    }

    return new Proxy(model, {
      get(target, prop, receiver) {
        const originalValue = Reflect.get(target, prop, receiver);

        if (typeof originalValue === 'function' && prop === 'predict') {
          return async function (...args) {
            const start = performance.now(); 
            
            let result;
            try {
             
              result = await originalValue.apply(this, args);
            } catch (modelError) {
              throw modelError; 
            }

            
            try {
              const latency = (performance.now() - start).toFixed(4);
              
              sdk.buffer.push({
                modelId: sdk.modelId,
                timestamp: getTimestamp(),
                latency: parseFloat(latency),
                input: deepClone(args[0]), 
                output: deepClone(result)   
              });
            } catch (sdkError) {
           
              console.warn("⚠️ [Guardrail SDK] Failed to capture vitals.", sdkError);
            }

            return result;
          };
        }
        return originalValue;
      }
    });
  }
}


export default new Guardrail();
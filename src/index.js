
import { deepClone, getTimestamp } from './utils/helpers.js';
import { DataBuffer } from './buffer.js';
import { Transport } from './transport.js'; 

const POSITIVE_LABELS = new Set(['approved', 'accept', 'accepted', 'yes', 'true', 'positive', 'allow']);
const NEGATIVE_LABELS = new Set(['rejected', 'reject', 'denied', 'no', 'false', 'negative', 'block']);

function isFiniteNumber(value) {
  return typeof value === 'number' && Number.isFinite(value);
}

function normalizeLabel(label) {
  if (typeof label !== 'string') {
    return null;
  }
  return label.trim().toLowerCase();
}

function inferValueFromLabel(label) {
  const normalized = normalizeLabel(label);
  if (!normalized) {
    return null;
  }
  if (POSITIVE_LABELS.has(normalized)) {
    return 1;
  }
  if (NEGATIVE_LABELS.has(normalized)) {
    return 0;
  }
  return null;
}

function defaultPredictionAdapter(output) {
  if (typeof output === 'boolean') {
    return {
      value: output ? 1 : 0,
      label: output ? 'true' : 'false',
      confidence: null,
      type: 'binary'
    };
  }

  if (isFiniteNumber(output)) {
    return {
      value: output,
      label: null,
      confidence: null,
      type: output >= 0 && output <= 1 ? 'probability' : 'numeric'
    };
  }

  if (output && typeof output === 'object') {
    const numericCandidate = [
      output.value,
      output.prediction,
      output.score,
      output.probability,
      output.confidence,
      output.logit
    ].find(isFiniteNumber);

    const label = output.label ?? output.status ?? output.class ?? null;
    const inferredFromLabel = inferValueFromLabel(label);
    const value = isFiniteNumber(numericCandidate)
      ? numericCandidate
      : (inferredFromLabel !== null ? inferredFromLabel : 0);

    const confidence = isFiniteNumber(output.confidence)
      ? output.confidence
      : (isFiniteNumber(output.probability) ? output.probability : null);

    return {
      value,
      label,
      confidence,
      type: output.type ?? (value >= 0 && value <= 1 ? 'probability' : 'numeric')
    };
  }

  return {
    value: 0,
    label: null,
    confidence: null,
    type: 'unknown'
  };
}

class Guardrail {
  constructor() {
    this.buffer = null;    
    this.transport = null; 
    this.modelId = null;
    this.apiKey = null;
    this.captureMethods = ['predict'];
    this.inputAdapter = (args) => args[0] ?? {};
    this.predictionAdapter = defaultPredictionAdapter;
    this.domain = 'standard';
    this.predictionType = 'binary';
    this.nodeName = 'SDK_Intercept';
    this.modelVersion = 'latest';
    this.extraMetadata = {};
  }

 
  init({
    apiKey,
    modelId,
    endpoint,
    captureMethods = ['predict'],
    inputAdapter,
    predictionAdapter,
    domain = 'standard',
    predictionType = 'binary',
    nodeName = 'SDK_Intercept',
    modelVersion = 'latest',
    metadata = {}
  }) {
    this.apiKey = apiKey;
    this.modelId = modelId;
    this.captureMethods = Array.isArray(captureMethods) && captureMethods.length > 0
      ? captureMethods
      : ['predict'];
    this.inputAdapter = typeof inputAdapter === 'function' ? inputAdapter : this.inputAdapter;
    this.predictionAdapter = typeof predictionAdapter === 'function' ? predictionAdapter : this.predictionAdapter;
    this.domain = typeof domain === 'string' && domain.trim() ? domain.trim() : 'standard';
    this.predictionType = typeof predictionType === 'string' && predictionType.trim() ? predictionType.trim() : 'binary';
    this.nodeName = typeof nodeName === 'string' && nodeName.trim() ? nodeName.trim() : 'SDK_Intercept';
    this.modelVersion = typeof modelVersion === 'string' && modelVersion.trim() ? modelVersion.trim() : 'latest';
    this.extraMetadata = metadata && typeof metadata === 'object' ? deepClone(metadata) : {};

  
    this.transport = new Transport({
      apiKey,
      modelId,
      endpoint,
      domain: this.domain,
      predictionType: this.predictionType,
      nodeName: this.nodeName,
      modelVersion: this.modelVersion
    });

    
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

        if (typeof originalValue === 'function' && sdk.captureMethods.includes(prop)) {
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
              const normalizedInput = deepClone(sdk.inputAdapter(args));
              const normalizedPrediction = deepClone(sdk.predictionAdapter(result));
              
              sdk.buffer.push({
                eventId: `${Date.now()}-${Math.random().toString(16).slice(2, 10)}`,
                modelId: sdk.modelId,
                timestamp: getTimestamp(),
                latencyMs: parseFloat(latency),
                inputFeatures: normalizedInput,
                prediction: normalizedPrediction,
                metadata: {
                  method: prop,
                  domain: sdk.domain,
                  prediction_type: sdk.predictionType,
                  node_name: sdk.nodeName,
                  model_version: sdk.modelVersion,
                  ...deepClone(sdk.extraMetadata)
                },
                // Legacy fields retained for backward compatibility with older workers.
                latency: parseFloat(latency),
                input: normalizedInput,
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
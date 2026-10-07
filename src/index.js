
import { deepClone, getTimestamp } from './utils/helpers.js';
import { DataBuffer } from './buffer.js';
import { Transport } from './transport.js'; 
import {
  DEFAULT_BATCH_SIZE, DEFAULT_FLUSH_INTERVAL_MS, DEFAULT_REQUEST_TIMEOUT_MS,
  DEFAULT_MAX_QUEUE_LIMIT, DEFAULT_MAX_RETRIES
} from './constants.js';

const activeGuardrails = new Set();
let exitHooksRegistered = false;

function registerExitHooks() {
  if (exitHooksRegistered || typeof process === 'undefined' || typeof process.on !== 'function') return;
  exitHooksRegistered = true;
  const shutdownAll = () => Promise.all([...activeGuardrails].map(instance => instance.shutdown()));
  process.on('beforeExit', () => { void shutdownAll(); });
  for (const [signal, exitCode] of [['SIGINT', 130], ['SIGTERM', 143]]) {
    process.on(signal, () => {
      shutdownAll().finally(() => process.exit(exitCode));
    });
  }
}

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

export class Guardrail {
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
    this.onError = null;
    this.shutdownPromise = null;
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
    metadata = {},
    onError,
    batchSize = DEFAULT_BATCH_SIZE,
    flushIntervalMs = DEFAULT_FLUSH_INTERVAL_MS,
    requestTimeoutMs = DEFAULT_REQUEST_TIMEOUT_MS,
    maxQueueLimit = DEFAULT_MAX_QUEUE_LIMIT,
    maxRetries = DEFAULT_MAX_RETRIES
  }) {
    if (typeof apiKey !== 'string' || !apiKey.trim()) throw new Error('apiKey is required and must not be empty.');
    if (typeof modelId !== 'string' || !modelId.trim()) throw new Error('modelId is required and must not be empty.');
    if (predictionType && !['probability', 'binary', 'multiclass', 'regression'].includes(predictionType)) {
      console.warn(`[Guardrail SDK] Unsupported predictionType: ${predictionType}`);
    }
    if (this.buffer) void this.buffer.shutdown();
    this.shutdownPromise = null;
    this.apiKey = apiKey;
    this.modelId = modelId;
    this.onError = typeof onError === 'function' ? onError : null;
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

  
    const transport = new Transport({
      apiKey,
      modelId,
      endpoint,
      domain: this.domain,
      predictionType: this.predictionType,
      nodeName: this.nodeName,
      modelVersion: this.modelVersion,
      requestTimeoutMs,
      maxRetries,
      onError: this.onError
    });
    this.transport = transport;

    this.buffer = new DataBuffer((batch) => transport.sendBatch(batch), {
      batchSize, flushIntervalMs, maxQueueLimit
    });
    activeGuardrails.add(this);
    registerExitHooks();

    console.log(`🛡️ [Guardrail] SDK Initialized for Model: ${modelId}`);
  }

  flush() {
    return this.buffer?.flush();
  }

  shutdown() {
    if (!this.buffer) return Promise.resolve();
    if (!this.shutdownPromise) {
      this.shutdownPromise = this.buffer.shutdown().finally(() => activeGuardrails.delete(this));
    }
    return this.shutdownPromise;
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
              if (sdk.onError) {
                try {
                  sdk.onError(sdkError, { type: 'adapter', modelId: sdk.modelId });
                } catch (callbackError) {
                  console.error('[Guardrail SDK] onError callback failed:', callbackError);
                }
              } else {
                console.warn("⚠️ [Guardrail SDK] Failed to capture vitals.", sdkError);
              }
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

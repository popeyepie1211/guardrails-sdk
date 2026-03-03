# guardrails-sdk

A lightweight Node.js SDK that wraps AI/ML model predictions to capture telemetry (input, output, latency) and sends batched vitals to a backend for monitoring and auditing.

## Features

- **Zero-interference wrapping** — Uses `Proxy` to intercept `predict()` calls without modifying your model code.
- **Automatic batching** — Buffers predictions and flushes in configurable batches (default: 50 items or every 5 seconds).
- **Non-blocking transport** — Sends telemetry in the background using HTTP so your model latency is unaffected.
- **Overflow protection** — Drops the oldest data point if the buffer exceeds its limit, preventing memory issues.

## Installation

```bash
npm install guardrails-sdk
```

## Quick Start

```js
import guardrail from 'guardrails-sdk';

// 1. Initialize the SDK with your credentials
guardrail.init({
  apiKey: 'YOUR_API_KEY',        // Your Guardrail API key
  modelId: 'my_model_v1',       // A unique identifier for this model
  endpoint: 'https://your-backend.example.com/v1/ingest' // Your ingestion endpoint
});

// 2. Define or import your AI model (must have a `predict` method)
const myModel = {
  predict: async (input) => {
    // ... your model logic ...
    return { label: 'positive', confidence: 0.95 };
  }
};

// 3. Wrap the model — this activates telemetry capture
const monitoredModel = guardrail.wrap(myModel);

// 4. Use the wrapped model exactly as before
const result = await monitoredModel.predict({ text: 'hello world' });
// The SDK captures { input, output, latency, timestamp } behind the scenes
```

## API Reference

### `guardrail.init(options)`

Initializes the SDK. Must be called before `wrap()`.

| Option     | Type   | Required | Description                                         |
|------------|--------|----------|-----------------------------------------------------|
| `apiKey`   | string | Yes      | Your API key for authentication with the backend.   |
| `modelId`  | string | Yes      | A unique identifier for the model being monitored.  |
| `endpoint` | string | No       | The backend ingestion URL. Defaults to `https://api.guardrail.ai/v1/ingest`. |

### `guardrail.wrap(model)`

Returns a proxied version of `model`. Any call to `.predict()` on the returned object will:
1. Execute the original prediction.
2. Record `{ modelId, timestamp, latency, input, output }` into the internal buffer.
3. Automatically flush the buffer when it reaches the batch size or the flush interval.

The original `predict()` return value is passed through unchanged.

## Deploying to npm

To publish this SDK so others can install it with `npm install guardrails-sdk`:

### 1. Create an npm account

Sign up at [npmjs.com](https://www.npmjs.com/signup) if you don't have one.

### 2. Authenticate locally

```bash
npm login
```

### 3. Publish

```bash
npm publish
```

> **Scoped package (optional):** If the name `guardrails-sdk` is taken, rename the package in `package.json` to `@your-scope/guardrails-sdk` and publish with:
> ```bash
> npm publish --access public
> ```

### 4. Automated publishing (CI/CD)

This repository includes a GitHub Actions workflow (`.github/workflows/publish.yml`) that publishes to npm automatically when you create a GitHub Release. To use it:

1. Go to **Settings → Secrets and variables → Actions** in your GitHub repo.
2. Add a secret named `NPM_TOKEN` with an npm automation token ([create one here](https://www.npmjs.com/settings/~/tokens)).
3. Create a new Release on GitHub — the workflow will publish the package to npm.

## Deploying the Ingestion Backend

The SDK sends telemetry to a backend endpoint. A reference implementation is included in `test/mock-server.js`. For production:

1. **Deploy the ingestion server** (e.g., on AWS, GCP, Railway, or Render).
2. **Set up Redis** for burst management (the server uses Redis `LPUSH` to queue batches).
3. **Point the SDK** at your production endpoint:

```js
guardrail.init({
  apiKey: 'YOUR_API_KEY',
  modelId: 'production_model_v2',
  endpoint: 'https://your-production-api.example.com/v1/ingest'
});
```

## Running Tests Locally

```bash
# Start the mock ingestion server (requires Redis running on localhost:6379)
npm run test:server

# In another terminal, run the mock model test
npm test
```

## License

ISC

## Installation

Install the SDK from npm:

```bash
npm install guardrails-sdk
```

## Quick Start

Instrument your ML model with Guardrails to capture predictions and vitals:

```javascript
import Guardrail from 'guardrails-sdk';

// Initialize with your API key (obtained from Guardrails dashboard)
Guardrail.init({
  apiKey: 'your-api-key',
  modelId: 'your-model-id',
  endpoint: 'https://api.guardrail.ai/v1/ingest', // Managed Guardrails backend
  domain: 'lending',
  predictionType: 'binary',
  nodeName: 'risk_classifier'
});

// Wrap your model's predict method
const model = Guardrail.wrap({
  predict: async (input) => {
    // Your ML model logic here
    return { score: 0.87, label: 'approved' };
  }
});

// Use your model—predictions are automatically captured
const result = await model.predict({ amount: 5000, credit_score: 720 });
console.log(result);
```

## Configuration

- `apiKey`: Your authentication key from the Guardrails dashboard.
- `modelId`: Unique identifier for your model.
- `endpoint`: Ingestion endpoint. Defaults to `https://api.guardrail.ai/v1/ingest` (managed service).
- `domain`: Model domain (e.g., `lending`, `fraud`, `recommendation`).
- `predictionType`: Either `binary` or `multiclass`.
- `nodeName`: Name of the decision node being monitored.

## Architecture

Guardrails uses a **managed SaaS backend model**:

- **SDK (npm package)**: Lightweight client that intercepts model predictions and sends telemetry.
- **Ingestion Service**: Hosted centrally; receives prediction batches and queues processing.
- **Worker**: Computes SHAP explainability and vitals; persists to TimescaleDB.
- **API**: Serves vitals and SHAP history via REST endpoints.
- **Dashboard**: Visualizes model performance and explainability.

You only need to install the SDK. Everything else runs on Guardrails' managed infrastructure.
   



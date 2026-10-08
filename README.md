## Installation

Install the SDK from npm:

```bash
npm install guardrails-sdk
```

## Register a model

From your project directory, create `guardrail.config.json` with the registration fields and paths to your local artifacts:

```json
{
  "apiBaseUrl": "http://127.0.0.1:8002",
  "model_id": "my_model",
  "model_name": "My Model",
  "domain": "standard",
  "prediction_type": "binary",
  "feature_columns": ["age", "group"],
  "numerical_features": ["age"],
  "categorical_features": ["group"],
  "quasi_identifier_columns": ["group"],
  "model_file": "./model.joblib",
  "historical_data_file": "./history.csv"
}
```

`apiBaseUrl` is the URL of your running Guardrails backend, not the SDK ingestion endpoint. The historical CSV must contain the configured feature and quasi-identifier columns and a `prediction` column. Optional config fields are `model_version`, `prediction_column`, `protected_attributes`, `preprocessor_file` (`.joblib` or `.pkl`), and `shap_background_file` (`.csv`). The model file must be `.joblib` or `.pkl`; the historical data file must be `.csv`. Artifact validation and baseline computation remain on the backend.

Run this after installing the SDK in your project:

```bash
npx guardrail register
```

The CLI calls `POST /api/models/register` and prints the returned API key once. Store the key in a secret manager or environment variable; the CLI never saves it. Do not place a key in `guardrail.config.json` or commit a key to source control. Registration is an explicit developer action; SDK initialization does not register a model. This registration endpoint is currently intended for trusted developers/operators, not public unauthenticated onboarding. `API_KEY_PEPPER` belongs only on the backend server.

## Quick Start

Instrument your ML model with Guardrails to capture predictions and vitals:

```javascript
import Guardrail from 'guardrails-sdk';

// Use the model ID and API key returned by `npx guardrail register`.
Guardrail.init({
  apiKey: process.env.GUARDRAIL_API_KEY,
  modelId: 'my_model',
  endpoint: 'http://localhost:3000/v1/ingest', // Ingestion service for the same deployment
  domain: 'standard',
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

- `apiKey`: The one-time authentication key returned by registration. Load it from a secret environment or secret manager.
- `modelId`: Unique identifier for your model.
- `endpoint`: Ingestion endpoint for the same Guardrails deployment where you registered the model. The SDK default is `https://api.guardrail.ai/v1/ingest`.
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
   



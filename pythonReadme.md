# Guardrail AI

Guardrail AI is a post-deployment AI governance framework designed to monitor machine learning models after they are deployed in production.

The goal of the framework is not only to detect model issues, but also to convert low-level monitoring signals into structured governance decisions that can be reviewed by humans or consumed by downstream systems.

Guardrail AI is divided into two major parts:

1. **Part A: Technical Monitoring Core**
2. **Part B: Digital Judge**

---

## 1. Project Objective

Modern machine learning models can degrade after deployment due to data drift, distribution shift, bias, privacy risks, adversarial inputs, infrastructure failures, or explainability degradation.

Guardrail AI addresses this problem by continuously monitoring deployed models and producing governance-ready outputs such as:

- Metric-level health status
- Threshold-based risk signals
- WDAG-based failure propagation
- Diagnosis
- Severity assessment
- Confidence score
- Human-readable verdict
- Recommended governance action
- Governance report

The framework is designed as a post-deployment governance layer. It does not replace model training, model serving, or deployment infrastructure. Instead, it observes deployed models and provides structured governance intelligence.

---

## 2. High-Level Architecture

The complete Guardrail AI pipeline follows this flow:

```text
SDK
    ↓
Redis Queue
    ↓
Worker Auditor
    ↓
Validator
    ↓
VitalsEngine
    ↓
Threshold Evaluator
    ↓
WDAG
    ↓
Digital Judge
    ↓
Governance Decision / Report
    ↓
TimescaleDB / FastAPI / Dashboard / Integrations

---

## 3. Part A: Technical Monitoring Core

Part A is responsible for computing and evaluating governance metrics.

Implemented components include:

- Validator
- VitalsEngine
- Threshold Evaluator
- WDAG
- Batch Manager
- Baseline Initializer
- Persistence Manager
- Heartbeat Monitor
- Configuration module

Part A receives production data batches and returns structured metric and status outputs.

Part A does **not** generate governance verdicts. It only performs technical monitoring and threshold evaluation.

---

## 4. Metrics Implemented in Part A

The VitalsEngine computes the following metrics centrally:

### Drift and Stability

- Population Stability Index (PSI)

### Fairness

- Statistical Parity
- Gini Coefficient

### Privacy

- Privacy Score

### Security

- L-infinity Norm
- Out-of-Distribution Score

### Transparency

- SHAP-based Transparency / Feature Importance

All metrics are computed once inside the VitalsEngine.

WDAG nodes do not compute metrics independently.

---

## 5. Threshold Evaluation

The Threshold Evaluator converts raw metric values into governance statuses.

Supported threshold types:

- Upper threshold
- Lower threshold
- Two-sided threshold
- Domain-aware threshold
- Persistence filtering

Supported domains:

- Healthcare
- Finance
- Standard

Healthcare and finance domains can be treated more strictly than standard domains because they are higher-risk deployment environments.

---

## 6. WDAG: Weighted Directed Acyclic Graph

The WDAG represents logical pipeline stages such as:

- Data
- Model
- Deployment

The WDAG is responsible for propagating risk status across connected components.

Implemented WDAG features include:

- Graph
- Node
- Executor
- Blast radius propagation
- Hysteresis
- Heartbeat monitoring
- Zombie node detection

Important design decision:

```text
WDAG does not compute governance metrics.
WDAG only receives evaluated node status and propagates impact.
---

## 9. Responsibility Boundary

Guardrail AI is designed with clear responsibility separation.

This module is responsible for:

- Validation
- Metric computation
- Threshold evaluation
- WDAG propagation
- Heartbeat monitoring
- Zombie node detection
- Governance diagnosis
- Severity assessment
- Governance recommendation
- Governance report generation

This module is **not** responsible for:

- Database schema design
- Redis deployment
- FastAPI implementation
- React dashboard implementation
- Slack notifications
- Jira ticket creation
- PagerDuty integration
- Kill-switch execution
- Model retraining execution
- Deployment rollback execution

The framework only recommends governance actions. It never executes external actions directly.

Downstream systems can later map recommendations such as:

- `INVESTIGATE_DRIFT`
- `REVIEW_FAIRNESS`
- `CHECK_INFRASTRUCTURE`
- `ISOLATE_MODEL`
- `RETRAIN_MODEL`
- `NOTIFY_OWNER`

to operational systems such as Jira, Slack, PagerDuty, deployment APIs, or model registry workflows.

---

## 10. Current Project Status

Completed:

- Part A monitoring core
- Validator
- VitalsEngine
- Metric computation
- Threshold evaluation
- Domain-aware thresholds
- Persistence filtering
- WDAG graph and node logic
- Blast radius propagation
- Heartbeat monitoring
- Zombie node detection
- Batch Manager
- Baseline Initializer
- Digital Judge reasoning layer
- Governance recommendation layer
- Governance report builder
- Unit tests for core modules
- Integrated Part A + Part B simulation using a real dataset

Handled by teammates / external modules:

- TimescaleDB persistence
- FastAPI API layer
- React dashboard
- Redis production deployment
- Webhooks
- Slack/Jira/PagerDuty mapping
- Kill-switch integration
- Deployment automation

---

## 11. Supported Model Types

Guardrail AI is designed for post-deployment monitoring and is not limited to models trained from CSV files.

The framework can monitor any model as long as production inference events can be converted into a structured tabular format containing:

- Input features
- Prediction output
- Model identifier
- Domain metadata
- Batch metadata
- Optional SHAP or explainability values

Supported model categories include:

### 11.1 Traditional Machine Learning Models

Examples:

- Logistic Regression
- Random Forest
- XGBoost
- LightGBM
- SVM
- Decision Trees
- Regression models
- Classification models

These models are the most direct fit because their inputs are usually structured features.

Typical use cases:

- Credit scoring
- Fraud detection
- Healthcare risk prediction
- Insurance risk modeling
- Recommendation ranking
- Churn prediction

### 11.2 Deep Learning Models with Structured Inputs

Guardrail AI can also monitor deep learning models when their input and output can be represented as structured features.

Examples:

- Tabular neural networks
- Time-series prediction models
- Embedding-based classifiers
- Multimodal models where extracted features are logged

The monitoring system does not need to know the internal model architecture. It only needs the inference input and output data.

### 11.3 Pretrained Models

Guardrail AI can monitor pretrained models even when the original training dataset is unavailable.

In this case, the framework requires a reference baseline created from one of the following:

- Validation data
- Calibration data
- Fine-tuning data
- Approved production reference window
- Domain-specific benchmark data

The original training dataset is useful but not mandatory.

### 11.4 Fine-Tuned Models

For fine-tuned models, Guardrail AI can use the fine-tuning dataset or validation dataset as the baseline.

This is suitable when the base model was trained externally, but the project team has access to:

- Fine-tuning samples
- Validation samples
- Evaluation samples
- Model input/output logs

The baseline should represent the expected deployment distribution.

### 11.5 Black-Box or API-Based Models

Guardrail AI can monitor black-box models if the system can log:

- Input features sent to the model
- Model prediction output
- Confidence score or probability when available
- Model ID or version
- Domain metadata

The model does not need to expose its weights or internal architecture.

However, some explainability metrics such as SHAP may require additional access or approximation methods.

---

## 12. Baseline Modes

Guardrail AI requires a baseline reference to compare production behavior against expected behavior.

A baseline does not always mean the original training dataset.

Supported baseline modes are:

### 12.1 Training Dataset Baseline

Used when the original training data is available.

This is the most straightforward baseline mode.

The baseline is computed from the training dataset and includes:

- Feature distributions
- Prediction distribution
- Metric reference values
- Threshold statistics

### 12.2 Validation Dataset Baseline

Used when training data is unavailable but validation data exists.

This is common for pretrained or externally supplied models.

The validation set should represent expected production behavior.

### 12.3 Fine-Tuning Dataset Baseline

Used when a pretrained model has been fine-tuned.

The fine-tuning dataset can act as the baseline if it reflects the deployment domain.

This is useful for models adapted to a specific organization, region, or task.

### 12.4 Calibration Dataset Baseline

Used when a small curated reference dataset is available.

This baseline is useful when:

- Training data is private
- Training data is too large
- Training data belongs to another organization
- Only representative samples are available

### 12.5 Production Reference Window Baseline

Used when no offline dataset is available.

In this mode, the system collects an initial approved production window and freezes it as the baseline.

Example reference windows:

- First 1,000 successful predictions
- First 24 hours of verified traffic
- First week of stable production traffic
- A manually approved production sample

This mode is useful for black-box or vendor-provided models.

### 12.6 Benchmark Dataset Baseline

Used when domain benchmark data is available.

This may be useful for research, testing, or evaluation when real production data is not yet available.
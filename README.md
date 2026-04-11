## Installation

Clone the repository and install dependencies.

```bash
git clone https://github.com/popeyepie1211/guardrails-sdk.git
cd guardrails-sdk

pip install -r requirements.txt
pip install -e .
```

* `pip install -r requirements.txt` installs all required external dependencies.
* `pip install -e .` installs the **guardrail_ai package in editable mode**, allowing local development and testing.

---

## Running Tests

All tests are located inside the `tests/` directory.

Run the test suite from the **project root directory** (same folder containing `pyproject.toml`):

```bash
pytest
```

or with verbose output:

```bash
pytest -v
```

This will automatically discover and run all tests in the `tests/` folder.

---
## TimescaleDB Config
 1. Start TimescaleDB using Docker
Run the following command to start a TimescaleDB container:

```bash
docker run -d \
--name timescale-guardrail \
-p 5432:5432 \
-e POSTGRES_PASSWORD=password \
timescale/timescaledb:latest-pg15
```
2. Connect to PostgreSQL
   ```bash
   docker exec -it timescale-guardrail psql -U postgres
   ```
   



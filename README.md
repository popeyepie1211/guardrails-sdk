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

## Quick Check

After installation, you should be able to import the package:

```python
import guardrail_ai
```

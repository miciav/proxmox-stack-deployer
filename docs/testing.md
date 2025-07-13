## 🧪 Testing

The project includes a comprehensive testing suite for the Python deployment script (`deploy.py`).

### Running Tests

**Install test dependencies:**
```bash
# Activate your virtual environment if you have one
source .venv/bin/activate

# Install the required packages
pip install -r requirements-test.txt
```

**Run all tests:**
```bash
python3 run_tests.py --all
```

**Run specific test categories:**
```bash
# Unit tests only
python3 run_tests.py --unit

# Integration tests only
python3 run_tests.py --integration

# Tests with coverage report
python3 run_tests.py --coverage

# Code quality checks (linting)
python3 run_tests.py --lint
```

**Direct `pytest` usage:**
```bash
# Run all tests with verbose output
pytest -v

# Run with coverage report
pytest --cov=deploy --cov-report=html
```

### Test Coverage

The test suite includes:
- **Unit Tests**: Test individual functions and argument parsing
- **Integration Tests**: Test complete deployment workflows
- **Error Handling**: Test edge cases and error conditions
- **Mocking**: All external commands are mocked to avoid side effects
- **CI/CD**: GitHub Actions workflow for automated testing

**Note**: The Python deployment script and tests are provided as-is and have not been fully tested in a production environment. Use with caution and validate thoroughly in your specific setup.

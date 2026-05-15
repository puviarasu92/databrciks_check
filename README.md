# databrciks_check

This is a sample project for Databricks checks and validation.

## Overview

This repository contains utility functions and tools for checking Databricks configurations and setups.

## Features

- Configuration validation
- Cluster health checks
- Workspace management utilities
- Data pipeline monitoring

## Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/puviarasu92/databrciks_check.git
cd databrciks_check
```

## Usage

```python
from databrciks_check import validate_config

# Example usage
config = load_config()
result = validate_config(config)
print(result)
```

## Requirements

- Python 3.8+
- databricks-cli
- pandas
- pyspark

---

# Databricks CI/CD Pipeline

CI/CD for Databricks SQL notebooks using **Databricks Asset Bundles** + **GitHub Actions**.

## Project Structure

```
├── .github/workflows/
│   ├── ci.yml              # PR validation & SQL linting
│   └── cd.yml              # Deploy to dev (push) / prod (release)
├── src/notebooks/
│   └── sample_etl.sql      # SQL notebook
├── databricks.yml           # DABs bundle configuration
├── .sqlfluff                # SQL linter config
└── README.md
```

## Prerequisites

1. **Databricks CLI v0.200+** – installed automatically in CI via `databricks/setup-cli`.
2. **Databricks Personal Access Token** (or OAuth M2M) for each workspace.
3. A GitHub repo with **Environments** configured (`dev`, `prod`).

## GitHub Secrets to Configure

| Secret | Description |
|---|---|
| `DATABRICKS_HOST_DEV` | Dev workspace URL (e.g. `https://adb-123.azuredatabricks.net`) |
| `DATABRICKS_TOKEN_DEV` | Dev workspace PAT |
| `CLUSTER_ID_DEV` | Existing cluster ID in dev |
| `DATABRICKS_HOST_PROD` | Prod workspace URL |
| `DATABRICKS_TOKEN_PROD` | Prod workspace PAT |
| `CLUSTER_ID_PROD` | Existing cluster ID in prod |
| `SP_NAME_PROD` | Service principal name for prod `run_as` |

## How It Works

### CI (Pull Requests)
1. **Validate** – `databricks bundle validate` checks the bundle config against the dev workspace.
2. **SQL Lint** – `sqlfluff lint` checks SQL style (non-blocking by default).

### CD (Deployments)
1. **Push to `main`** → deploys to **dev** automatically.
2. **GitHub Release published** → deploys to **prod** (with manual approval via GitHub Environment protection rules).

## Local Development

```bash
# Install Databricks CLI
# See: https://docs.databricks.com/dev-tools/cli/install.html

# Validate the bundle locally
databricks bundle validate --target dev

# Deploy to dev
databricks bundle deploy --target dev

# Run the job
databricks bundle run sample_etl_job --target dev
```

## Adding New Notebooks

1. Add your `.sql` file under `src/notebooks/`.
2. Add a new job or task in `databricks.yml` under `resources.jobs`.
3. Open a PR — CI will validate and lint automatically.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

This project is licensed under the MIT License.

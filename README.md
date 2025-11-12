# PlanX CRM scripts

This repository contains Python scripts for syncing data from the PlanX to our Notion CRM,

---

## Setup & installation

This project uses [uv](https://github.com/astral-sh/uv) for package and environment management.

1.  **Install `uv`:**
    ```bash
    pip install uv
    ```

2.  **Create the virtual environment:**
    ```bash
    uv venv
    ```

3.  **Activate the environment:**
    * **Mac/Linux:**
        ```sh
        source .venv/bin/activate
        ```
    * **Windows:**
        ```bash
        .venv\Scripts\activate
        ```

4.  **Install dependencies:**
    ```bash
    uv sync
    ```

---

## Linting & formatting

We use [Ruff](https://docs.astral.sh/ruff/) to keep the code clean and consistent. Ruff is ran as a step in our CI.

**To format all files:**
```bash
ruff format .
```

**To check for errors and auto-fix them:**
```bash
ruff check --fix .
```

---

## Scripts

### `sync-planx-services`

#### What it does
Syncs the list of online services per team from the PlanX GraphQL API into the "PlanX Live Services" Notion database.

#### How it runs
This script is run via a GitHub Action.
  * **On a schedule:** Runs automatically every night at midnight UTC.
  * **Manually:** Can be triggered at any time by going to the **Actions** tab in this repo and running the "Sync PlanX teams to Notion CRM" workflow.

#### Local development
To run this locally you'll need a populated `.env` file (see `.env.example`). Values can be found via the Open Systems Lab 1Password vault.

Once you've activated the virtual environment and installed the necessary dependencies (see above), you can run the following in your terminal -

```bash
uv run src/sync-planx-services/main.py
```
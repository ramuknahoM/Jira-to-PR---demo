# AIDLC Flow Demo

A small React + FastAPI MVP that makes the AIDLC engineering workflow visible and keeps each external integration behind a replaceable boundary.

## Run locally

1. Copy `backend/.env.example` to `backend/.env` and configure the integrations you intend to use.
2. Start the API:
   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   uvicorn app.main:app --reload --port 8000
   ```
3. Start the UI in a second terminal:
   ```powershell
   cd frontend
   npm install
   npm run dev
   ```

Open `http://localhost:5173`.

## Available demo flow

Create a workflow with a Jira key, retrieve the configured Jira issue, inspect deterministic requirement and complexity analysis, choose an available model, approve or revise a versioned plan, then analyze the configured repository and create an AI branch. The UI presents explicit blocked states where a live integration has not yet been configured.

## Configuration and limitations

`JIRA_BASE_URL`, `JIRA_USERNAME`, and `JIRA_API_TOKEN` are required for issue retrieval. `REPOSITORY_PATH` must reference a local Git repository for branch creation. `GEMINI_API_KEY` enables Gemini as the selectable provider, though generation remains intentionally connector-ready in this milestone. MongoDB, implementation execution, test generation, commits, and PR creation are defined as boundaries but require their corresponding configured adapters before the workflow can truthfully complete those actions.

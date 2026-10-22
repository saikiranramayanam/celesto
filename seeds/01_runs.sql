-- Initialize runs ledger schema
CREATE TABLE IF NOT EXISTS runs (
    run_id VARCHAR(255) PRIMARY KEY,
    sandbox_name VARCHAR(255) NOT NULL UNIQUE,
    problem_id VARCHAR(255) NOT NULL,
    state VARCHAR(50) NOT NULL CHECK (state IN ('created', 'ready', 'running', 'succeeded', 'failed', 'deleted')),
    execution_target VARCHAR(50) NOT NULL CHECK (execution_target = 'celesto_sandbox'),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Seed row required by the specification:
-- Sandbox name 'sbx-seeddemo1', state 'deleted', execution_target 'celesto_sandbox'
-- Re-running the SQL does not duplicate it.
INSERT INTO runs (run_id, sandbox_name, problem_id, state, execution_target)
VALUES (
    'run-seed-001',
    'sbx-seeddemo1',
    'issue-failing-test-repro',
    'deleted',
    'celesto_sandbox'
)
ON CONFLICT (run_id) DO UPDATE SET
    sandbox_name = EXCLUDED.sandbox_name,
    problem_id = EXCLUDED.problem_id,
    state = EXCLUDED.state,
    execution_target = EXCLUDED.execution_target;

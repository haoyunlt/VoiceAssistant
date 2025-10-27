-- Drop trigger
DROP TRIGGER IF EXISTS update_tasks_updated_at ON ai_orchestrator.tasks;

-- Drop function
DROP FUNCTION IF EXISTS ai_orchestrator.update_updated_at_column();

-- Drop indexes
DROP INDEX IF EXISTS ai_orchestrator.idx_tasks_tenant_status;
DROP INDEX IF EXISTS ai_orchestrator.idx_tasks_pending_priority;
DROP INDEX IF EXISTS ai_orchestrator.idx_tasks_completed_at;
DROP INDEX IF EXISTS ai_orchestrator.idx_tasks_created_at;
DROP INDEX IF EXISTS ai_orchestrator.idx_tasks_tenant;
DROP INDEX IF EXISTS ai_orchestrator.idx_tasks_user;
DROP INDEX IF EXISTS ai_orchestrator.idx_tasks_conversation;
DROP INDEX IF EXISTS ai_orchestrator.idx_tasks_priority;
DROP INDEX IF EXISTS ai_orchestrator.idx_tasks_status;
DROP INDEX IF EXISTS ai_orchestrator.idx_tasks_type;

-- Drop table
DROP TABLE IF EXISTS ai_orchestrator.tasks;

-- Drop schema
DROP SCHEMA IF EXISTS ai_orchestrator CASCADE;

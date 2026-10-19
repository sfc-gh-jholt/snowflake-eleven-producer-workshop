-- Complete teardown: removes ALL workshop objects.
-- Run 07_stop.sql first to suspend tasks and avoid cancellation race conditions.
-- This is irreversible. All workshop data, procedures, tasks, and history are lost.

USE DATABASE ELEVEN_PRODUCER_LAB;
USE SCHEMA DEMO;

-- Suspend tasks to prevent new executions.
ALTER TASK IF EXISTS CAPTURE_ROOT SUSPEND;
ALTER TASK IF EXISTS WATCHDOG_TASK SUSPEND;
ALTER TASK IF EXISTS INVENTORY_TASK SUSPEND;
ALTER TASK IF EXISTS PUBLISH_TASK SUSPEND;

-- Clear DMF schedule before drop. Schedule propagation can lag up to 10 minutes;
-- dropping the database while a serverless DMF evaluation is queued can incur cost.
ALTER VIEW IF EXISTS CURRENT_ENTITIES SET DATA_METRIC_SCHEDULE = '';

-- Suspend the optional dynamic table if the DT_LAB schema was installed.
ALTER DYNAMIC TABLE IF EXISTS ELEVEN_PRODUCER_LAB.DT_LAB.PREPARED SUSPEND;

-- Verify no tasks are still executing before proceeding.
SELECT NAME, STATE FROM TABLE(SNOWFLAKE.INFORMATION_SCHEMA.TASK_HISTORY(
  SCHEDULED_TIME_RANGE_START => DATEADD('hour', -1, CURRENT_TIMESTAMP()),
  RESULT_LIMIT => 100))
WHERE DATABASE_NAME = 'ELEVEN_PRODUCER_LAB' AND STATE = 'EXECUTING';
-- Expect zero rows. If any tasks are executing, wait for them to finish or cancel manually.

DROP DATABASE IF EXISTS ELEVEN_PRODUCER_LAB;
DROP WAREHOUSE IF EXISTS ELEVEN_PRODUCER_WH;

-- After this, rerun 00_setup.sql for a fresh sandbox.

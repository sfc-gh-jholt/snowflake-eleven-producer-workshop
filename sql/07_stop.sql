USE DATABASE ELEVEN_PRODUCER_LAB;
USE SCHEMA DEMO;
ALTER TASK CAPTURE_ROOT SUSPEND;
ALTER TASK WATCHDOG_TASK SUSPEND;
ALTER TASK INVENTORY_TASK SUSPEND;
ALTER TASK PUBLISH_TASK SUSPEND;
SHOW TASKS IN SCHEMA ELEVEN_PRODUCER_LAB.DEMO;
-- If 04_optional_dmfs.sql was installed, run this separately:
-- ALTER VIEW CURRENT_ENTITIES SET DATA_METRIC_SCHEDULE = '';
-- Suspension does not cancel a run already executing. Inspect task history.
-- No destructive teardown is included: retain evidence and review deletion yourself.
-- OPTIONAL, separate approval/installation step. Enterprise Edition required.
-- Review the measures, expectations and hourly serverless monitoring cost first.
-- Not required for synchronous RUN_STAGE quality gates. Do not run twice.
USE DATABASE ELEVEN_PRODUCER_LAB;
USE SCHEMA DEMO;
SHOW DATA METRIC FUNCTIONS LIKE 'NULL_COUNT' IN SCHEMA SNOWFLAKE.CORE;
SHOW DATA METRIC FUNCTIONS LIKE 'DUPLICATE_COUNT' IN SCHEMA SNOWFLAKE.CORE;
ALTER VIEW CURRENT_ENTITIES ADD DATA METRIC FUNCTION
 SNOWFLAKE.CORE.NULL_COUNT ON (ENTITY_ID)
 EXPECTATION no_missing_entity_id (VALUE = 0);
ALTER VIEW CURRENT_ENTITIES ADD DATA METRIC FUNCTION
 SNOWFLAKE.CORE.DUPLICATE_COUNT ON (ENTITY_ID)
 EXPECTATION one_current_row_per_entity (VALUE = 0);
ALTER VIEW CURRENT_ENTITIES SET DATA_METRIC_SCHEDULE='60 MINUTE';
SELECT * FROM TABLE(SYSTEM$EVALUATE_DATA_QUALITY_EXPECTATIONS(
 REF_ENTITY_NAME=>'ELEVEN_PRODUCER_LAB.DEMO.CURRENT_ENTITIES'));
-- CHECKPOINT: exactly 2 expectation rows; VALUE=0 and EXPECTATION_VIOLATED=FALSE.
-- This is direct evaluation, not proof of a recurring scheduled measurement.
-- An expectation violation does not automatically block a task or roll back data.
-- This script does not configure email, external integrations or task suspension.
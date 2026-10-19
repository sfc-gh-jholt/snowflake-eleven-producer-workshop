-- READ ONLY. Run before setup. Inspect every result; no grants are applied here.
-- Keep this worksheet/output private: context and grants can identify your account.
SELECT CURRENT_ACCOUNT_NAME() AS ACCOUNT_NAME,CURRENT_ROLE() AS INSTALLER_ROLE,
 CURRENT_WAREHOUSE() AS SESSION_WAREHOUSE,CURRENT_VERSION() AS VERSION;
SHOW DATABASES LIKE 'ELEVEN_PRODUCER_LAB';
-- Expect zero rows. If occupied: STOP; choose a new namespace throughout the scripts.
SHOW WAREHOUSES LIKE 'ELEVEN_PRODUCER_WH';
-- Expect zero rows. Setup creates this dedicated X-Small warehouse; do not reuse blindly.
SET LAB_OWNER_ROLE = CURRENT_ROLE();
SHOW GRANTS TO ROLE IDENTIFIER($LAB_OWNER_ROLE);
-- Installer: CREATE DATABASE and CREATE WAREHOUSE on ACCOUNT (or inherited rights).
-- Task owner: EXECUTE TASK on ACCOUNT; USAGE on the lab warehouse.
-- New DB/schema owner creates the contained objects. ACCOUNTADMIN is for a disposable
-- instructor sandbox only, not the production task owner. SHOW GRANTS lists direct
-- grants: absent rows do NOT prove an inherited privilege is absent. Have your admin
-- confirm role inheritance and task-owner privileges before running the workshop.
-- Administrator action if needed (review role first; not automatically executed):
-- GRANT EXECUTE TASK ON ACCOUNT TO ROLE <approved_lab_owner>;
-- Optional DMFs: confirm Enterprise Edition or higher in Snowsight Account details.
-- Portable SQL has no generally available CURRENT_EDITION() function. Do not infer
-- edition from function visibility. An admin's edition confirmation is a manual gate.
SHOW DATA METRIC FUNCTIONS LIKE 'NULL_COUNT' IN SCHEMA SNOWFLAKE.CORE;
SHOW DATA METRIC FUNCTIONS LIKE 'DUPLICATE_COUNT' IN SCHEMA SNOWFLAKE.CORE;
-- Function visibility is a capability probe, NOT proof of edition or attach permission.
-- Check EXECUTE DATA METRIC FUNCTION on ACCOUNT and DMF access for the monitor owner.
-- After setup, SHOW GRANTS ON WAREHOUSE ELEVEN_PRODUCER_WH; verify owner/USAGE.
-- CHECKPOINT: free names + administrator-confirmed privileges = core path ready.
-- Edition or DMF permission unknown? Skip 04, continue the core workshop.

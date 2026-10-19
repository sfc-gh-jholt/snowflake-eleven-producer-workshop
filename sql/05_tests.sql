-- Install named scenarios after 00-03. This file defines tests; it does not run them.
-- Run 05_run_tests.sql ONCE, or call each scenario in order as documented.
-- Scenarios share a progressive fixture: individually callable, NOT independent resets.
-- Keep tasks suspended. Stop at the first unexpected error; do not wrap calls in a transaction.
USE DATABASE ELEVEN_PRODUCER_LAB;
USE SCHEMA DEMO;
USE WAREHOUSE ELEVEN_PRODUCER_WH;
CREATE OR REPLACE PROCEDURE ASSERT_TEST(P_NAME VARCHAR,P_OK BOOLEAN,P_DETAIL VARCHAR)
RETURNS VARCHAR LANGUAGE SQL AS $$
DECLARE failed EXCEPTION(-20010,'Assertion failed: inspect TEST_RESULTS');
BEGIN
 INSERT INTO TEST_RESULTS(TEST_NAME,PASSED,DETAIL)
 VALUES(:P_NAME,COALESCE(:P_OK,FALSE),:P_DETAIL);
 IF(NOT COALESCE(P_OK,FALSE)) THEN RAISE failed; END IF;
 RETURN 'PASS';
END; $$;

CREATE OR REPLACE PROCEDURE TEST_01_RECEIPTS_AND_STREAM()
RETURNS VARCHAR LANGUAGE SQL AS $$
DECLARE outcome VARCHAR; before_rows NUMBER; after_rows NUMBER; value_count NUMBER;
 caught BOOLEAN DEFAULT FALSE;
BEGIN
 SELECT COUNT(*) INTO :value_count FROM PRODUCER_EVENTS;
 IF(value_count<>0) THEN
  CALL ASSERT_TEST('Scenario 1 requires fresh events',FALSE,'Use a fresh sandbox, not a replay of the tests');
 END IF;
 CALL RUN_STAGE('2025-01-06','V1','INVENTORY',FALSE) INTO :outcome;
 CALL ASSERT_TEST('No receipts waits',:outcome='WAIT',:outcome);
 INSERT INTO PRODUCER_EVENTS(PRODUCER,PROCESS_DATE,SOURCE_VERSION,STATUS,WATERMARK,ROW_COUNT)
 SELECT PRODUCER,'2025-01-06','V1','SUCCESS','2025-01-06',0
 FROM DEPENDENCIES WHERE PRODUCER<>'P11';
 -- SELECT INTO scripting variables is read-only. INSERT SELECT FROM stream is NOT.
 SELECT COUNT(*) INTO :before_rows FROM COMPLETION_STREAM;
 SELECT COUNT(*) INTO :after_rows FROM COMPLETION_STREAM;
 CALL ASSERT_TEST('SELECT leaves bookmark unchanged',:before_rows=10 AND :after_rows=10,'Two plain SELECTs');
 BEGIN
  CALL CAPTURE_EVENTS(TRUE);
 EXCEPTION WHEN OTHER THEN
  IF(SQLCODE=-20001) THEN caught:=TRUE; ELSE RAISE; END IF;
 END;
 SELECT COUNT(*) INTO :after_rows FROM COMPLETION_STREAM;
 SELECT COUNT(*) INTO :value_count FROM RECEIPTS;
 CALL ASSERT_TEST('Capture rollback preserves stream',:caught AND :after_rows=10 AND :value_count=0,'Injected exception only');
 CALL CAPTURE_EVENTS(FALSE);
 SELECT COUNT(*) INTO :after_rows FROM COMPLETION_STREAM;
 CALL ASSERT_TEST('Commit consumes stream',:after_rows=0,'Durable receipts retained');
 CALL RUN_STAGE('2025-01-06','V1','INVENTORY',FALSE) INTO :outcome;
 CALL ASSERT_TEST('Ten of eleven waits',:outcome='WAIT',:outcome);
 RETURN 'PASS: 5 assertions; ten receipts captured, no business completion';
END; $$;

CREATE OR REPLACE PROCEDURE TEST_02_READINESS_CONTRACT()
RETURNS VARCHAR LANGUAGE SQL AS $$
DECLARE outcome VARCHAR; value_count NUMBER;
BEGIN
 SELECT COUNT(*) INTO :value_count FROM RECEIPTS;
 IF(value_count<>10) THEN
  CALL ASSERT_TEST('Scenario 2 prerequisite',FALSE,'Run scenario 1 once first');
 END IF;
 INSERT INTO PRODUCER_EVENTS(PRODUCER,PROCESS_DATE,SOURCE_VERSION,STATUS,WATERMARK,ROW_COUNT)
 VALUES('P01','2025-01-06','V1','SUCCESS','2025-01-06',0),
 ('P11','2025-01-05','V1','SUCCESS','2025-01-05',1),
 ('P11','2025-01-06','V2','SUCCESS','2025-01-06',1),
 ('P11','2025-01-06','V1','SUCCESS','2025-01-05',1),
 ('P11','2025-01-06','V1','FAILED','2025-01-06',1);
 CALL CAPTURE_EVENTS(FALSE);
 CALL RUN_STAGE('2025-01-06','V1','INVENTORY',FALSE) INTO :outcome;
 CALL ASSERT_TEST('Duplicates and mismatched receipts cannot unlock',:outcome='WAIT',:outcome);
 INSERT INTO PRODUCER_EVENTS(PRODUCER,PROCESS_DATE,SOURCE_VERSION,STATUS,WATERMARK,ROW_COUNT)
 VALUES('P11','2025-01-06','V1','SUCCESS','2025-01-06',0);
 CALL CAPTURE_EVENTS(FALSE);
 UPDATE FILE_MANIFEST SET STATUS='PARTIAL' WHERE PROCESS_DATE='2025-01-06';
 CALL RUN_STAGE('2025-01-06','V1','INVENTORY',FALSE) INTO :outcome;
 CALL ASSERT_TEST('Incomplete file waits',:outcome='WAIT',:outcome);
 UPDATE FILE_MANIFEST SET STATUS='SUCCESS' WHERE PROCESS_DATE='2025-01-06';

 RETURN 'PASS: 2 assertions; all inputs ready, no business completion';
END; $$;

CREATE OR REPLACE PROCEDURE TEST_03_QUALITY_AND_DAY_ONE()
RETURNS VARCHAR LANGUAGE SQL AS $$
DECLARE outcome VARCHAR; value_count NUMBER; caught BOOLEAN DEFAULT FALSE;
BEGIN
 SELECT COUNT(*) INTO :value_count FROM READINESS
 WHERE PROCESS_DATE='2025-01-06' AND MISSING_PARENTS=0 AND FILE_READY;
 IF(value_count<>1) THEN
  CALL ASSERT_TEST('Scenario 3 prerequisite',FALSE,'Run scenarios 1 and 2 first');
 END IF;
 -- Corrupt a key, verify the hard gate, then repair before retry.
 UPDATE SOURCE_ENTITIES SET ENTITY_ID=1 WHERE PROCESS_DATE='2025-01-06' AND ENTITY_ID=100;
 caught:=FALSE;
 BEGIN
  CALL RUN_STAGE('2025-01-06','V1','INVENTORY',FALSE);
 EXCEPTION WHEN OTHER THEN
  IF(SQLCODE=-20003) THEN caught:=TRUE; ELSE RAISE; END IF;
 END;
 SELECT COUNT(*) INTO :value_count FROM COMPLETIONS;
 CALL ASSERT_TEST('Duplicate keys block before business writes',:caught AND :value_count=0,'Quality exception required');
 DELETE FROM SOURCE_ENTITIES WHERE PROCESS_DATE='2025-01-06' AND ENTITY_ID=1;
 INSERT INTO SOURCE_ENTITIES VALUES('2025-01-06','V1',1,TRUE,FALSE),('2025-01-06','V1',100,TRUE,FALSE);
 CALL RUN_STAGE('2025-01-06','V1','INVENTORY',FALSE);
 CALL RUN_STAGE('2025-01-06','V1','PUBLISH',FALSE);
 SELECT COUNT(*) INTO :value_count FROM HISTORY WHERE VALID_TO IS NULL;
 CALL ASSERT_TEST('Zero-row producer receipts accepted',:value_count=100,'Day 1 published');
 CALL RUN_STAGE('2025-01-06','V1','INVENTORY',FALSE) INTO :outcome;
 CALL ASSERT_TEST('Inventory replay is no-op',:outcome='NOOP',:outcome);

 RETURN 'PASS: 3 assertions; day one published';
END; $$;

CREATE OR REPLACE PROCEDURE TEST_04_ROLLBACK_AND_RECOVERY()
RETURNS VARCHAR LANGUAGE SQL AS $$
DECLARE value_count NUMBER; after_rows NUMBER; caught BOOLEAN DEFAULT FALSE;
BEGIN
 SELECT COUNT(*) INTO :value_count FROM COMPLETIONS;
 IF(value_count<>2) THEN
  CALL ASSERT_TEST('Scenario 4 prerequisite',FALSE,'Run scenario 3 first');
 END IF;
 INSERT INTO PRODUCER_EVENTS(PRODUCER,PROCESS_DATE,SOURCE_VERSION,STATUS,WATERMARK,ROW_COUNT)
 SELECT PRODUCER,'2025-01-07','V1','SUCCESS','2025-01-07',101 FROM DEPENDENCIES;
 CALL CAPTURE_EVENTS(FALSE);
 CALL RUN_STAGE('2025-01-07','V1','INVENTORY',FALSE);
 caught:=FALSE;
 BEGIN
  CALL RUN_STAGE('2025-01-07','V1','PUBLISH',TRUE);
 EXCEPTION WHEN OTHER THEN
  IF(SQLCODE=-20004) THEN caught:=TRUE; ELSE RAISE; END IF;
 END;
 SELECT COUNT(*) INTO :value_count FROM HISTORY WHERE VALID_TO IS NULL;
 SELECT COUNT(*) INTO :after_rows FROM COMPLETIONS WHERE PROCESS_DATE='2025-01-07' AND JOB='PUBLISH';
 CALL ASSERT_TEST('Failed publish retains last good output',:caught AND :value_count=100 AND :after_rows=0,'No false completion');
 SELECT COUNT(*) INTO :after_rows FROM COMPLETION_STREAM;
 CALL ASSERT_TEST('Business failure after capture has empty stream',:after_rows=0,'Recovery must use pending work, not new events');
 CALL WATCHDOG('2025-01-07 14:00:00');
 SELECT COUNT(*) INTO :value_count FROM HISTORY;
 CALL ASSERT_TEST('Watchdog recovers durable pending work',:value_count=111,'No additional producer event');
 RETURN 'PASS: 3 assertions; day two recovered with no new receipt';
END; $$;

CREATE OR REPLACE PROCEDURE TEST_05_REPLAY_AND_PARITY()
RETURNS VARCHAR LANGUAGE SQL AS $$
DECLARE value_count NUMBER; after_rows NUMBER;
BEGIN
 SELECT COUNT(*) INTO :value_count FROM COMPLETIONS;
 IF(value_count<>4) THEN
  CALL ASSERT_TEST('Scenario 5 prerequisite',FALSE,'Run scenario 4 first');
 END IF;
 INSERT INTO PRODUCER_EVENTS(PRODUCER,PROCESS_DATE,SOURCE_VERSION,STATUS,WATERMARK,ROW_COUNT)
 SELECT PRODUCER,'2025-01-08','V1','SUCCESS','2025-01-08',101 FROM DEPENDENCIES;
 CALL CAPTURE_EVENTS(FALSE);
 CALL DRAIN_STAGE('INVENTORY');
 CALL DRAIN_STAGE('PUBLISH');
 CALL DRAIN_STAGE('INVENTORY');
 CALL DRAIN_STAGE('PUBLISH');
 SELECT COUNT(*) INTO :value_count FROM HISTORY;
 SELECT COUNT(*) INTO :after_rows FROM HISTORY WHERE VALID_TO IS NULL;
 CALL ASSERT_TEST('Unchanged day and replay preserve history',:value_count=111 AND :after_rows=101,'111 versions / 101 current');
 SELECT COUNT(*) INTO :value_count FROM INVENTORY WHERE DAY_COUNT<>IFF(ENTITY_ID=101,2,3);
 CALL ASSERT_TEST('Counters increment once per business date',:value_count=0,'No duplicate processing');
 SELECT COUNT(*) INTO :value_count FROM COMPLETIONS;
 CALL ASSERT_TEST('Two jobs times three dates',:value_count=6,'Six business completions');
 CALL CAPTURE_EVENTS(FALSE);
 SELECT COUNT(*) INTO :value_count FROM COMPLETIONS;
 CALL ASSERT_TEST('Empty wake-up is harmless',:value_count=6,'No new work');
 -- Independent row-level oracle: compare both directions, not only totals.
 SELECT COUNT(*) INTO :value_count FROM (
 WITH expected_history AS (
  SELECT SEQ4()+1 AS ENTITY_ID,FALSE AS ELIGIBLE,'2025-01-06'::DATE AS VALID_FROM,
   IFF(ENTITY_ID<=10,'2025-01-07'::DATE,NULL) AS VALID_TO
  FROM TABLE(GENERATOR(ROWCOUNT=>100))
  UNION ALL
  SELECT IFF(SEQ4()=10,101,SEQ4()+1),TRUE,'2025-01-07'::DATE,NULL
  FROM TABLE(GENERATOR(ROWCOUNT=>11))
 ), missing_rows AS (SELECT * FROM expected_history MINUS SELECT * FROM HISTORY),
 extra_rows AS (SELECT * FROM HISTORY MINUS SELECT * FROM expected_history)
 SELECT * FROM missing_rows UNION ALL SELECT * FROM extra_rows
 );
 CALL ASSERT_TEST('Exact historical rows match oracle',:value_count=0,'Bidirectional row comparison including interval endpoints');
 SELECT COUNT(*) INTO :value_count FROM INVENTORY;
 SELECT COALESCE(SUM(DAY_COUNT),0) INTO :after_rows FROM INVENTORY;
 CALL ASSERT_TEST('Inventory cardinality and total',:value_count=101 AND :after_rows=302,'101 entities / 302 total days');
 RETURN 'PASS: 6 assertions; final parity checked';
END; $$;
# Security and publication scope

This repository contains generated records and generic producer names only. It does not contain customer files, real account identifiers, connection profiles, query-history exports, credentials or recorded customer evidence.

Use a sandbox. Owner-rights procedures can write their tables; task owners execute with their privileges. Production requires a deliberately scoped owner/operator model and restricted writes to candidate, completion, dependency and request tables. The sample does not provision a least-privilege role hierarchy.

Do not commit secrets, local connection configuration, real data or Snowflake results. Review any screenshots, logs and issue attachments before making them public. An ignored directory is not a substitute for reviewing staged files.

There are no outbound notifications or external integrations in this sample. Optional DMF monitoring uses Snowflake-managed compute and requires appropriate edition/privileges. No public sharing of Snowflake data is configured.

Do not report secrets through public issues. Report defects with synthetic reproductions and sanitized error descriptions.
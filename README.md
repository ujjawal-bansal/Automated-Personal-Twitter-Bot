# Personal daily X agent

The agent selects one original standalone post for @AtheXTheist per Asia/Kolkata calendar day. Current affairs compete with evergreen observations. A dated story needs independent reporting and passes a trend-exclusion check. If research is unavailable the writer can use an evergreen idea. Failed quality checks can leave a day empty.

## Architecture

- GitHub Actions checks the daily slot twice an hour. PostgreSQL reserves the account and date. The local runner uses the same reservation.
- Five publisher RSS feeds supply dated summaries. The model sees these as untrusted evidence. Timely ideas must identify two different publishers, supply literal evidence from each and pass the separate review for source independence, claim support and X trend overlap. This verifies against summaries only. An editor model can still misjudge evidence.
- Gemini proposes topics, writes up to three drafts per selected topic, then evaluates factual support, argument novelty, voice and specificity. Bounded retries use the configured model order. The profile in agent/profile.py is derived from the four Phase 1 documents. Engagement cannot change it.
- Drafts and evaluations stay in the private ledger. Console output in Actions contains status only. The publisher uses user-context OAuth and verifies the X user ID. Optional public-domain illustrations can be enabled with AGENT_COMMONS_IMAGES=true. The legacy card renderer and collection remain available separately.
- The ledger commits the intended post before the only X write. After a timeout the next run searches the account timeline for the same text. An inconclusive lookup leaves that slot held. A crash between persisting intent and sending can therefore cost a post. There is no backfill after midnight.
- The agent records available X metrics after 48 hours. Six comparable measured posts are required before a median format, topic or hour rate can influence selection. No exposure denominator means no rate. Time exploration stays inside the configured window.
- data/history.json is an import of historic bot posts. data/report.md and data/weights.json describe the legacy system. The new runtime stores state in PostgreSQL. The historical handoff describes the preceding deployment.

## Deployment

Use Python 3.12+, PostgreSQL 15+ and the psql client on PATH. The database role must be able to create its three tables and write rows. Restrict database access and enable provider backups. For a hosted database use its TLS connection string, including its recommended certificate verification settings. GitHub standard Ubuntu runners have a PostgreSQL client.

1. Set GitHub Actions secrets DATABASE_URL, GEMINI_API_KEY, X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET and SCHEDULE_SEED. Configure credentials for the account ID in the workflow. Tokens need read and write access. No passwords or keys belong in source control.
2. Verify the configured Gemini model is available to the project. Override with the Actions variable GEMINI_MODELS (a comma-separated model list). The existing repository defaults are tried otherwise. The model receives private drafts and public source excerpts. Review the provider's data handling for your chosen API tier.
3. Require the test workflow to pass, including its disposable PostgreSQL service. Run the daily workflow manually in dry-run mode while AGENT_ENABLED is unset. Shadow evaluates a candidate without database writes or X posts. For a private local preview, create a venv, install requirements and run ./run_local.sh dry-run.
4. Identify any active publisher for this X account. The Mac checkout previously inspected pointed to VashuVats/x-bot, a distinct repository. Disable or redirect competing scheduled dispatches before enabling this one. A legacy client outside this database cannot participate in its daily limit. Start on the next Kolkata day if an older deployment may already have posted today.
5. On the deployed default branch set the Actions repository variable AGENT_ENABLED=true. After this cutover the workflow publishes autonomously. A backup scheduler can dispatch this workflow in auto mode. Never run another independent publisher for the same account. Verify the first real receipt on a normal publishing day.
6. To stop future sends, switch AGENT_ENABLED to false and stop any in-flight run. Reconcile any pending intent before re-enabling. Keep the database when upgrading or rolling back.

The default target window is noon to 4 pm IST. The agent can catch up until 23:55 on the same date. POST_START_HOUR and POST_END_HOUR override the window. The current schedule uses two wakes per hour and does research only when a slot is acquired. A day permits three work leases; each has a 12-call model budget. Provider failures can still incur costs. Set billing caps in provider consoles.

## Monitoring and validation

Use the Actions run status and private agent_slots, agent_memory and agent_events tables. Check for skipped days, stale working slots and unresolved sending records. Revoked credentials, exhausted credits and prolonged database outages require external action. Diagnostics omit draft bodies and credentials.

Run python -m unittest discover -s tests -v with the dependencies installed. Set TEST_DATABASE_URL to a disposable PostgreSQL database to enable concurrency and restart tests. Mock tests send no posts. The dry-run, auto and learn-now workflow dispatches share the same implementation as the CLI. Legacy local force-mode aliases retain the daily cap.

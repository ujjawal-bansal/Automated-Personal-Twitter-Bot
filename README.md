# Personal daily X agent

The agent selects one original standalone post for @AtheXTheist per Asia/Kolkata calendar day. Current affairs compete with evergreen observations. A dated story needs independent reporting and passes a trend-exclusion check. If research is unavailable the writer can use an evergreen idea. Failed quality checks can leave a day empty.

## Architecture

- GitHub Actions checks the daily slot twice an hour. An encrypted file on the account’s Git state branch reserves the date. The local runner uses the same reservation.
- Five publisher RSS feeds supply dated summaries. The model sees these as untrusted evidence. Timely ideas must identify two different publishers, supply literal evidence from each and pass the separate review for source independence, claim support and X trend overlap. This verifies against summaries only. An editor model can still misjudge evidence.
- Gemini proposes topics, writes up to three drafts per selected topic, then evaluates factual support, argument novelty, voice and specificity. Bounded retries use the configured model order. The profile in agent/profile.py is derived from the four Phase 1 documents. Engagement cannot change it.
- Drafts and evaluations exist in memory during generation. Console output in Actions contains status only. The publisher uses user-context OAuth and verifies the X user ID. Optional public-domain illustrations can be enabled with AGENT_COMMONS_IMAGES=true. The legacy card renderer and collection remain available separately.
- The ledger commits a SHA-256 fingerprint of the intended text and its topic before the only X write. After a timeout the next run searches the account timeline for the same text. An inconclusive lookup leaves that slot held. A crash between persisting intent and sending can therefore cost a post. There is no backfill after midnight.
- The current snapshot holds one posting slot and up to ten recent topic labels. The publisher uses the Kolkata date to retire yesterday’s slot. Topic labels help the next draft avoid repetition. New draft text, review notes and engagement metrics are never written to the state branch.
- data/history.json is an import of historic bot posts. data/report.md and data/weights.json describe the legacy system. The runtime stores state on the same repository’s agent-state-<account ID> branch. The historical handoff describes the preceding deployment.

## Deployment

Use Python 3.12+ and Git. The workflow uses its built-in repository token with contents write permission. Branch rules must allow it to create and replace its dedicated state branch. The main branch needs no force-push permission. Local live runs need push access to the same origin. Each state transition is committed before continuing. Each update replaces the snapshot with one parentless commit using an explicit Git lease. If another writer changes the branch first, the bot reloads before trying again. Keep the state branch when cleaning up old branches. Losing or rolling it back can allow duplicate sends.

State is encrypted using the account’s X_API_SECRET by default. Keep this key stable. To rotate X credentials without changing the encryption key, set AGENT_STATE_KEY to the original X_API_SECRET before rotating. Alternatively set a separate random AGENT_STATE_KEY before the first live run. State commit times and sizes are visible. The state branch points to one snapshot. Git hosts and existing clones can temporarily retain unreferenced encrypted objects. Existing public history supplies up to ten initial topic labels and any same-day posting receipt. Any installation that actually used the previous SQL backend must transfer its posting history and resolve outstanding sends before enabling this version.

1. Set GitHub Actions secrets GEMINI_API_KEY, X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET and SCHEDULE_SEED. Configure credentials for the account ID in the workflow. Tokens need read and write access. No passwords or keys belong in source control.
2. Verify the configured Gemini model is available to the project. Override with the Actions variable GEMINI_MODELS (a comma-separated model list). The existing repository defaults are tried otherwise. The model receives private drafts and public source excerpts. Review the provider's data handling for your chosen API tier.
3. Require the test workflow to pass, including its temporary Git remote concurrency test. Run the daily workflow manually in dry-run mode while AGENT_ENABLED is unset. Shadow evaluates a candidate without state writes or X posts. For a private local preview, create a venv, install requirements and run ./run_local.sh dry-run.
4. Identify any active publisher for this X account. The Mac checkout previously inspected pointed to VashuVats/x-bot, a distinct repository. Disable or redirect competing scheduled dispatches before enabling this one. A legacy client outside this repository ledger cannot participate in its daily limit. Start on the next Kolkata day if an older deployment may already have posted today.
5. On the deployed default branch set the Actions repository variable AGENT_ENABLED=true. After this cutover the workflow publishes autonomously. A backup scheduler can dispatch this workflow in auto mode. Never run another independent publisher for the same account. Verify the first real receipt on a normal publishing day.
6. To stop future sends, switch AGENT_ENABLED to false and stop any in-flight run. Check today’s sending slot before re-enabling. Keep the state branch and its encryption key when upgrading or rolling back.

The default target window is noon to 4 pm IST. The agent can catch up until 23:55 on the same date. POST_START_HOUR and POST_END_HOUR override the window. The current schedule uses two wakes per hour and does research only when a slot is acquired. A day permits three work leases; each has a 12-call model budget. Provider failures can still incur costs. Set billing caps in provider consoles.

## Monitoring and validation

Use the Actions run status and the current encrypted posting slot. Check for skipped days, stale working slots and unresolved sending records. Revoked credentials, exhausted credits and prolonged GitHub outages require external action. Diagnostics omit draft bodies and credentials.

Run python -m unittest discover -s tests -v with the dependencies installed. The concurrency and restart tests create an isolated local Git remote. Mock tests send no posts. The dry-run and auto workflow dispatches share the same implementation as the CLI. Legacy local force-mode aliases retain the daily cap.

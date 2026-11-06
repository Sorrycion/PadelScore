-- 📄 Jornada summary (a PDF): an admin asked to email it to the tournament's players.
-- The hourly email job sends it to each account with an email and a player in the
-- tournament (recaps on), within Azure's limits, for 3 days after the request; asking
-- again restarts those 3 days. sent_emails (kind 'summary') keeps it from going twice.

CREATE TABLE summary_requests (
    matchday_id INTEGER PRIMARY KEY REFERENCES matchdays(id) ON DELETE CASCADE,
    requested_by INTEGER REFERENCES users(id),
    requested_at TEXT NOT NULL DEFAULT (datetime('now'))
);

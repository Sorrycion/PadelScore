-- Every email the app tries to send (main.deliver), sent or not, for the admins'
-- 📬 Emails page: when (UTC) and on which league day, to whom, which kind (recap,
-- reminder, test-recap, test-reminder, test), its subject, and how it went (sent,
-- failed, throttled = over Azure's sending limit) with the error.

CREATE TABLE email_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sent_at TEXT NOT NULL DEFAULT (datetime('now')),
    day TEXT NOT NULL,
    organization_id INTEGER REFERENCES organizations(id),
    user_id INTEGER REFERENCES users(id),
    address TEXT NOT NULL,
    kind TEXT NOT NULL,
    matchday_id INTEGER,
    subject TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('sent', 'failed', 'throttled')),
    error TEXT
);
CREATE INDEX email_log_day ON email_log (organization_id, day);

-- Email (app/mailer.py, Azure Communication Services): each account chooses whether it
-- gets its jornada recap by email (on by default; /me and every email's unsubscribe
-- link turn it off), and the emails already sent are recorded so none goes twice.
-- sent_emails.matchday_id has no foreign key: deleting a jornada deletes its rows.

ALTER TABLE users ADD COLUMN email_recaps INTEGER NOT NULL DEFAULT 1;

CREATE TABLE sent_emails (
    kind TEXT NOT NULL,                                   -- 'recap'
    user_id INTEGER NOT NULL REFERENCES users(id),
    matchday_id INTEGER NOT NULL,
    sent_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (kind, user_id, matchday_id)
);

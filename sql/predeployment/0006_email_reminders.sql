-- Game-day reminder emails (main.send_reminders): the morning of a jornada, each account
-- that plays it gets its court, sets, rivals and chances. On by default; /me and the
-- email's unsubscribe link turn it off. Sent ones go in sent_emails (kind 'reminder').

ALTER TABLE users ADD COLUMN email_reminders INTEGER NOT NULL DEFAULT 1;

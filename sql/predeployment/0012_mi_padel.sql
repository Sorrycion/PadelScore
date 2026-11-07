-- 🏠 Mi pádel: every player account's own private space (an organization with an owner).
-- owner_id: the account it belongs to (NULL for clubs). Only the owner, the accounts with
--   a player in it (friends who joined by invitation) and super admins can open it.
-- invite_code: the secret of its invitation link (/invite/<code>).
ALTER TABLE organizations ADD COLUMN owner_id INTEGER REFERENCES users(id);
ALTER TABLE organizations ADD COLUMN invite_code TEXT;
CREATE UNIQUE INDEX organizations_owner ON organizations (owner_id) WHERE owner_id IS NOT NULL;
CREATE UNIQUE INDEX organizations_invite ON organizations (invite_code) WHERE invite_code IS NOT NULL;
-- players.created_by: the account that created this player by writing its name in a
--   friendly; while no account claims it, it's in that account's "Mis amistades sin
--   cuenta" with a link to claim it (/claim/<player>/<token>).
ALTER TABLE players ADD COLUMN created_by INTEGER REFERENCES users(id);
CREATE INDEX players_created_by ON players (created_by) WHERE created_by IS NOT NULL;

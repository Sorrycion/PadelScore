-- Three new tournament types (app/formats.py):
--   Retas: one jornada in rounds; winners move up a court, losers down.
--   Rey de la cancha: the winning pair stays on court, the loser goes to the end of the line.
--   Escalafón: a ladder of fixed pairs that challenge pairs above them; best of 3 sets.
-- matches.round: the round of a Retas jornada, or the match number of a Rey jornada.
-- matches.sets_detail: an Escalafón match's sets ("6-4, 3-6, 10-8"); its
--   team_a_games / team_b_games then hold the sets won (2-1).
-- ladder_pairs: an Escalafón's pairs, in their starting order (seed: the draw, then the
--   order they joined); active = 0 once a pair leaves (the ones below move up).
-- queue_pairs: a Rey de la cancha jornada's pairs, in the order they line up.

INSERT INTO rule_types (id, code, name) VALUES
    (5, 'retas', 'Retas'),
    (6, 'rey_cancha', 'Rey de la cancha'),
    (7, 'escalafon', 'Escalafón');

ALTER TABLE matches ADD COLUMN round INTEGER;
ALTER TABLE matches ADD COLUMN sets_detail TEXT;

CREATE TABLE ladder_pairs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
    player1_id INTEGER NOT NULL REFERENCES players(id),
    player2_id INTEGER NOT NULL REFERENCES players(id),
    seed INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);
CREATE INDEX ladder_pairs_tournament ON ladder_pairs (tournament_id);

CREATE TABLE queue_pairs (
    matchday_id INTEGER NOT NULL REFERENCES matchdays(id) ON DELETE CASCADE,
    slot INTEGER NOT NULL,
    player1_id INTEGER NOT NULL REFERENCES players(id),
    player2_id INTEGER NOT NULL REFERENCES players(id),
    PRIMARY KEY (matchday_id, slot)
);

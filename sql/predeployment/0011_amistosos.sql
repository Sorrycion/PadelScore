-- 🤝 Amistosos: an organization's friendly games, as one tournament per organization.
-- Its players are every player of the organization (by rule, not listed in
-- tournament_players). The tournament itself is created with the first friendly
-- (app/main.py: friendlies_tournament), each day's friendlies make one jornada, and a
-- set won scores 1 point (0 for a loss).
INSERT INTO rule_types (id, code, name) VALUES (8, 'amistosos', 'Amistosos');

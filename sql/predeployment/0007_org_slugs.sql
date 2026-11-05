-- Each organization gets a slug: its name in its URLs (/nene/tournaments/4), so a link
-- shows that organization only and keeps the browsing inside it. Lowercase, spaces and
-- URL characters turned into dashes; names that clash with the app's own paths get
-- "-org". New organizations get theirs from orgs.slugify() (accents removed too).

ALTER TABLE organizations ADD COLUMN slug TEXT;

UPDATE organizations SET slug = lower(replace(replace(replace(replace(replace(trim(name),
    ' ', '-'), '/', '-'), '?', '-'), '#', '-'), '.', '-'));

UPDATE organizations SET slug = slug || '-org' WHERE slug IN (
    'static', 'enter', 'login', 'logout', 'lang', 'rules', 'orgs', 'me', 'health', 'signup',
    'join', 'sw.js', 'r', 'install', 'tasks', 'unsubscribe', 'welcome', 'standings',
    'tournaments', 'players', 'matchdays', 'matches', 'medals', 'courts', 'users');

CREATE UNIQUE INDEX organizations_slug ON organizations (slug);

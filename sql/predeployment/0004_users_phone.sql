-- Accounts get an optional cell phone: the country (ISO code from app/countries.py, e.g.
-- 'MX'; several countries share +1, so the code is kept, not the dialing number) and
-- the number's digits without it. Only the account and admins see it.

ALTER TABLE users ADD COLUMN phone_country TEXT;
ALTER TABLE users ADD COLUMN phone TEXT;

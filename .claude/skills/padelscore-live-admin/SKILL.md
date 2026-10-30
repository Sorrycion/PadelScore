---
name: padelscore-live-admin
description: Inspect or administer the live PadelScore database on Azure through the Kudu API, using the personal subscription's token. Use it to look up organizations, accounts or counts, check pending pre-deployment SQL, back up the database, or create a super admin or organization outside the app's UI.
---

# Live PadelScore administration

The live SQLite database is `/home/data/padelscore.db` on App Service
`padelscore-sorrycion`. Kudu's `/api/command` runs **one program without a shell**: no
`&&`, pipes, or `VAR=x cmd` (use `env VAR=x cmd`). Kudu has `python3` (3.11) but no
`sqlite3` CLI.

```bash
T=$(az account get-access-token --subscription af2fe534-02d1-4920-8bea-24efdcac3083 --resource https://management.azure.com/ --query accessToken -o tsv)
K=https://padelscore-sorrycion.scm.azurewebsites.net
run() { curl -s -X POST -H "Authorization: Bearer $T" -H "Content-Type: application/json" "$K/api/command" -d "$1"; }
```

## Read-only checks

```bash
curl -s https://padelscore-sorrycion.azurewebsites.net/health    # live commit + applied SQL files
run '{"command":"python3 -c \"import sqlite3;c=sqlite3.connect(\\\"/home/data/padelscore.db\\\");print(c.execute(\\\"SELECT id,role,username,organization_id FROM users\\\").fetchall(), c.execute(\\\"SELECT id,name FROM organizations\\\").fetchall(), c.execute(\\\"SELECT COUNT(*) FROM players\\\").fetchone(), c.execute(\\\"SELECT COUNT(*) FROM matches\\\").fetchone(), c.execute(\\\"PRAGMA integrity_check\\\").fetchone())\"","dir":"/home"}'
run '{"command":"ls -l /home/data","dir":"/home"}'
```

**Never print** `users.password`, `users.password_plain`, `secret`, or the old
`organizations.admin_password*` columns. To check that a password still works, compare it
in Python and print only True or False.

## Back up first (before any write)

```bash
run '{"command":"cp -p /home/data/padelscore.db /home/data/padelscore-backup-<yyyy-mm-dd><letter>.db","dir":"/home"}'
```

Check that the copy exists with `ls -l` before going on. The pipeline makes
`padelscore-backup-<date>-gh.db` backups by itself.

## Running Python from the repo on Kudu (migrations, accounts)

`app/__init__.py`, `app/db.py`, `app/migrate.py`, `app/users.py` and `app/orgs.py` only
need the standard library.

1. Upload the files you need:
   `curl -X PUT -H "Authorization: Bearer $T" -H "If-Match: *" --data-binary @<file> "$K/api/vfs/<tmpdir>/<file>"`.
   Nested folders are created as needed. For migrations, also upload
   `sql/predeployment/*.sql`.
2. Run, with `"dir": "/home/<tmpdir>"`:
   - `env PADELSCORE_DB=/home/data/padelscore.db python3 -m app.migrate --status`
     (read-only);
   - `env PADELSCORE_DB=/home/data/padelscore.db python3 -m app.migrate` (applies the
     pending files; back up first);
   - `env PADELSCORE_DB=/home/data/padelscore.db python3 -m app.orgs superadmin "user" "pw"`,
     or `create "Org" "admin" "pw"`, or `password "user" "pw"`.
3. Delete the folder: `curl -X DELETE -H "Authorization: Bearer $T" -H "If-Match: *" "$K/api/vfs/<tmpdir>/?recursive=true"`.

Prefer the app for account work: super admins manage organizations on `/orgs` and every
account on 🔑 Cuentas (`/users`). Passwords come from the user. Don't invent them, and
don't write them to files, tests, commits or memory.

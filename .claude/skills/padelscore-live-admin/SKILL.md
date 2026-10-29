---
name: padelscore-live-admin
description: Inspect or administer the live PadelScore database on Azure. Use to look up organizations or counts, back up the database, or create an organization or super admin outside the app's UI. It runs commands through the Kudu API with the personal subscription's token.
---

# Live PadelScore administration

The live SQLite database is `/home/data/padelscore.db` on App Service
`padelscore-sorrycion`. Kudu's `/api/command` runs **one program without a shell**:
no `&&`, pipes, or `VAR=x cmd` (use `env VAR=x cmd`). Kudu has `python3` (3.11).

```bash
T=$(az account get-access-token --subscription af2fe534-02d1-4920-8bea-24efdcac3083 --resource https://management.azure.com/ --query accessToken -o tsv)
K=https://padelscore-sorrycion.scm.azurewebsites.net
run() { curl -s -X POST -H "Authorization: Bearer $T" -H "Content-Type: application/json" "$K/api/command" -d "$1"; }
```

## Read-only checks

```bash
run '{"command":"python3 -c \"import sqlite3;c=sqlite3.connect(\\\"/home/data/padelscore.db\\\");print(c.execute(\\\"SELECT id,name,admin_user FROM organizations\\\").fetchall())\"","dir":"/home"}'
run '{"command":"ls -l /home/data","dir":"/home"}'
```

Never print password hashes, secrets or `admin_password_plain`. To check that a
password still works, compare it in Python and print only True or False.

## Back up first (before any write)

```bash
run '{"command":"cp -p /home/data/padelscore.db /home/data/padelscore-backup-<yyyy-mm-dd><letter>.db","dir":"/home"}'
```

Check that the copy exists with `ls -l` before going on.

## Organizations and super admins

The super admin can do this in the app at `/orgs` (create an organization, see and
change its admin user and password). For the CLI, `app/orgs.py` needs only the
standard library:

1. Upload `app/__init__.py`, `app/db.py` and `app/orgs.py` with
   `PUT $K/api/vfs/<tmpdir>/app/<file>` (header `If-Match: *`).
2. Run `env PADELSCORE_DB=/home/data/padelscore.db python3 -m app.orgs create "Name" "user" "password"`
   with `"dir": "/home/<tmpdir>"`. The subcommands are `create`, `password` and
   `superadmin`.
3. Delete `<tmpdir>`.

Passwords come from the user. Don't invent them, and don't write them to files, tests
or commits.

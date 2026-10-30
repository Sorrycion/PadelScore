# Deploy

`main` is protected: changes arrive through pull requests. Every push to `main`,
including a merge, deploys to https://padelscore-sorrycion.azurewebsites.net via
`.github/workflows/deploy.yml`.

```mermaid
flowchart LR
    A[Branch + commit] --> B[Push branch]
    B --> C[Pull request to main]
    C --> D["CI: test (pytest)"]
    D -- pass --> E[Merge]
    E --> F["CI on main: test again"]
    F --> G["Back up live DB<br/>/home/data/padelscore-backup-DATE-gh.db"]
    G --> P["Pre-deployment SQL:<br/>pending files of sql/predeployment"]
    P --> H[Zip deploy via Kudu + restart]
    H --> I["Wait until /health reports this commit"]
```

- **Azure login:** the service principal `padelscore-github` logs in through OpenID
  Connect, with no stored password. Its role is Website Contributor on the web app
  only. GitHub sends the subject
  `repo:Sorrycion@28118944/PadelScore@1432403444:environment:production`, which must
  match the federated credential `github-production-ids`.
- **Knowing the new version is live:** the pipeline writes the commit to `app/VERSION`
  inside the zip, and `/health` returns it, with the applied SQL files. After the
  restart the old instance keeps answering for a little while, so the last step waits
  until `/health` shows the new commit.
- **Repository secrets:** `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`.
- **The live database** is SQLite in `/home/data/padelscore.db`.
- **Pre-deployment SQL:** the pipeline uploads `app/db.py`, `app/migrate.py` and
  `sql/predeployment/*.sql` to a temporary Kudu folder. It runs
  `python3 -m app.migrate --status`, then `python3 -m app.migrate`, against the live
  database, and deletes the folder. If a file fails, the run stops before the deploy,
  and that file's changes are rolled back. The app runs the same thing when it starts,
  so local databases catch up too.
- **Manual deploy** (fallback, when GitHub Actions can't be used): see the skill
  `.claude/skills/padelscore-deploy`.

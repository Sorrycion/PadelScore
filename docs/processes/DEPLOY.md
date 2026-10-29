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
    G --> H[Zip deploy via Kudu + restart]
    H --> I["Check /enter answers 200"]
```

- **Azure login:** the service principal `padelscore-github` logs in through OpenID
  Connect, with no stored password. Its role is Website Contributor on the web app
  only. GitHub sends the subject
  `repo:Sorrycion@28118944/PadelScore@1432403444:environment:production`, which must
  match the federated credential `github-production-ids`.
- **Repository secrets:** `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`.
- **The live database** is SQLite in `/home/data/padelscore.db`. Migrations run on
  startup (`db.init_db`).
- **Manual deploy** (fallback, when GitHub Actions can't be used): see the skill
  `.claude/skills/padelscore-deploy`.

---
name: padelscore-deploy
description: Ship a PadelScore change to the live Azure site. Use when the user says push, deploy, commit and deploy, or ship. main is protected, so the change goes through a branch and a pull request, and the GitHub Actions pipeline deploys on merge. A manual Kudu zip deploy is the fallback.
---

# Deploying PadelScore

Live site: https://padelscore-sorrycion.azurewebsites.net (Azure App Service
`padelscore-sorrycion`, resource group `padelscore-rg`). Only use the personal
subscription `af2fe534-02d1-4920-8bea-24efdcac3083`. Never touch the work subscriptions
("Dev-Test Subscription", "Avea Production"), and never change the default az
subscription.

## Normal path: pull request → automatic deploy

1. Run the tests (all must pass). The scratchpad venv used before may be gone; if so,
   use `.venv/Scripts/python.exe -m pytest -q` after
   `pip install -r requirements-dev.txt`.
2. `git switch -c <topic>/<short-name>` from an up-to-date `main`, then commit. Commit
   messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
3. Push the branch. Git for this repo authenticates as **Sorrycion** through
   `gh auth token --user Sorrycion` (repo-local credential helper), whichever gh account
   is active.
4. Open the PR:
   `GH_TOKEN=$(gh auth token --user Sorrycion) gh pr create -R Sorrycion/PadelScore --base main --head <branch> --title ... --body ...`.
   The body ends with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
5. The user merges it (or asks you to). The merge runs `.github/workflows/deploy.yml`,
   which does:
   - test,
   - back up the database to `/home/data/padelscore-backup-<date>-gh.db`,
   - zip deploy and restart,
   - check that `/enter` answers 200.
6. Watch it: `GH_TOKEN=$(gh auth token --user Sorrycion) gh run list -R Sorrycion/PadelScore -L 3`,
   then `gh run view <id>`.

Pushing `.github/workflows/*` needs the `workflow` scope on Sorrycion's gh token. It
was added on 2026-10-28; if a push is refused for that, the user runs
`gh auth switch -u Sorrycion`, then `gh auth refresh -h github.com -s workflow`, then
switches back to `julio-curiel-kipu-13`.

## Fallback: manual deploy through Kudu

Only when Actions can't be used, and only if the user asks. The az default account is
the work one, so `az webapp deploy` and `az rest` give 403. Use a bearer token instead:

```bash
T=$(az account get-access-token --subscription af2fe534-02d1-4920-8bea-24efdcac3083 --resource https://management.azure.com/ --query accessToken -o tsv)
K=https://padelscore-sorrycion.scm.azurewebsites.net
# 1. Back up (one command per call, no shell: no && or pipes), then check with ls -l /home/data
curl -s -X POST -H "Authorization: Bearer $T" -H "Content-Type: application/json" "$K/api/command" \
  -d '{"command":"cp -p /home/data/padelscore.db /home/data/padelscore-backup-<date><letter>.db","dir":"/home"}'
# 2. Deploy
git archive --format=zip -o deploy.zip HEAD
curl -s -w "%{http_code}" -X POST -H "Authorization: Bearer $T" --data-binary @deploy.zip "$K/api/zipdeploy"
# 3. Restart, or the old version keeps running
az webapp restart --subscription af2fe534-02d1-4920-8bea-24efdcac3083 -g padelscore-rg -n padelscore-sorrycion -o none
```

Then poll the live site until the change shows.

## Never

- Commit `padelscore.db`, `.venv` or secrets.
- Put real credentials in tests, commits or command output (use `-o none`).
- Change Azure app settings or secrets yourself: the auto-mode classifier blocks it.
  Give the user the command instead.

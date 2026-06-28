# GitHub Private Repository Setup

This repo is prepared to be pushed as a private GitHub repository.

## Option A — GitHub CLI

From the repository root:

```bash
git status
gh auth login
gh repo create splat-facade-baker --private --source=. --remote=origin --push
```

If you want to create it under an organization:

```bash
gh repo create <org>/splat-facade-baker --private --source=. --remote=origin --push
```

## Option B — GitHub web UI

1. Create a new private repository on GitHub.
2. Do not initialize it with README, license or `.gitignore` because this repo already contains them.
3. Copy the remote URL.
4. Run:

```bash
git remote add origin git@github.com:<owner>/splat-facade-baker.git
git branch -M main
git push -u origin main --tags
```

## Option C — HTTPS remote

```bash
git remote add origin https://github.com/<owner>/splat-facade-baker.git
git branch -M main
git push -u origin main --tags
```

## Recommended repository settings

- Visibility: Private.
- Default branch: `main`.
- Enable issues.
- Enable discussions only if useful.
- Protect `main` once more contributors join.
- Require CI before merging once CI is stable.
- Do not commit private datasets, source GLBs, model weights or generated training runs.

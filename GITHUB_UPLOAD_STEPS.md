# Upload OEM Key Finder 8989 To GitHub

Project folder:

```powershell
C:\Users\rawes\Documents\Codex\2026-05-07\you-are-a-tool-developer-that\8989
```

## 1. Create A New Empty GitHub Repo

Go to GitHub and create a new empty repository.

Do not add a README, `.gitignore`, or license on GitHub because this project already has local files.

## 2. Run These Commands

Replace `YOUR_USERNAME` and `YOUR_REPO_NAME` with your real GitHub info.

```powershell
cd "C:\Users\rawes\Documents\Codex\2026-05-07\you-are-a-tool-developer-that\8989"

git init
git add .
git commit -m "Build OEM key finder app"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git push -u origin main
```

## 3. Important Private Files

Keep `.gitignore` in the project. It prevents these from being uploaded:

```text
data/private/
data/search_history.json
out/
__pycache__/
*.pyc
```

That protects subscriber emails and local test results.

## 4. Run The App Locally

After downloading or cloning the repo later:

```powershell
cd "C:\Users\rawes\Documents\Codex\2026-05-07\you-are-a-tool-developer-that\8989"
.\run-vin-key-web.ps1 -Port 8989
```

Then open:

```text
http://localhost:8989
```

# Install the futuristic profile README

1. Download and extract `talebulislam-github-profile-package.zip`.
2. Open your profile repository: `https://github.com/talebulislam/talebulislam`.
3. Copy the **contents** of the extracted `profile-readme-package` folder into the repository root, merging the `assets/`, `scripts/`, and `.github/` folders. Replace the existing `README.md`.
4. Commit and push the files. The `Refresh GitHub Profile Metrics` workflow should start automatically on `main` or `master`.
5. If it does not start, open the repository **Actions** tab → **Refresh GitHub Profile Metrics** → **Run workflow**.
6. If the action can generate the SVGs but cannot push them, open **Settings → Actions → General → Workflow permissions** and allow **Read and write permissions**.

No personal access token or extra secret is required: the workflow uses the repository's built-in `GITHUB_TOKEN`.

## How fresh is the data?

GitHub Actions refreshes the dashboard every six hours and after relevant README/workflow changes. This is near-live scheduled data, not second-by-second streaming. The profile README can display the last generated snapshot while GitHub processes newer activity.

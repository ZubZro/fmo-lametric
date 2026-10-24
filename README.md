# FMO LaMetric feed

This repository fetches FMO's public arrivals/departures XML, selects the next three arrivals and next three departures, and publishes `data.json` in LaMetric's predefined JSON format.

## Setup
1. Create a public GitHub repository.
2. Upload this package's files, preserving folders: `.github/workflows/update-feed.yml` and `scripts/build_feed.py`.
3. Open **Settings → Pages** and set **Source** to **GitHub Actions**.
4. Open **Actions → Update FMO LaMetric feed → Run workflow**.
5. After a successful run, use `https://YOUR-USERNAME.github.io/YOUR-REPOSITORY/data.json`.
6. In My Data DIY choose **HTTP Poll**, enter the URL, and select **Predefined (LaMetric format)**.

The workflow runs every five minutes, but scheduled GitHub jobs can be delayed.

## Important
The output URL is public and contains public flight information only. The script currently treats `ATD_TIME` or completed status codes as an indication that a flight has already operated. Verify the first output against FMO's own display before relying on it.

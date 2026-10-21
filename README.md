# KOGAS pipeline pressure archive

Source: https://www.kogas.or.kr/site/koGas/pressureInfo.do?Key=1040204000000

Archives the seven public KOGAS station pressures (MPa) four times a day in Singapore time. Each run adds a row to `data/kogas_pressures.csv` (or replaces that day's slot upon a re-run). Source date is stored separately from actual capture time, since the published readings may be daily snapshots.

## Setup

1. Create a GitHub repository (public or private).
2. Copy **all** files, including `.github/workflows/kogas_pressure.yml`, into the repository default branch.
3. In repository **Settings -> Actions -> General -> Workflow permissions**, choose **Read and write permissions** to permit CSV commits. If an organization policy blocks this, use an appropriately scoped token or change the policy.
4. In **Actions**, enable workflows if prompted, and test **Archive KOGAS pipeline pressures -> Run workflow**.
5. Inspect **Actions** job logs and `data/kogas_pressures.csv`. If extraction fails because KOGAS changed its HTML structure, the script exits with an error and does not write invalid rows.

## Schedule (Singapore UTC+8)

| Singapore time | UTC cron hour |
| --- | --- |
| 07:00 SGT | 23:00 UTC (previous day) |
| 12:00 SGT | 04:00 UTC |
| 17:00 SGT | 09:00 UTC |
| 22:00 SGT | 14:00 UTC |

GitHub-hosted scheduled workflows can run late or occasionally be skipped; they are not guaranteed to execute at exact minute 0. The capture timestamp records the actual run time.

## Local testing

```bash
python -m pip install -r requirements.txt
python scrape_kogas.py --slot manual
# Or test with a saved HTML page:
python scrape_kogas.py --html-file saved_kogas_page.html
```

CSV output columns: `capture_date_sgt,capture_time_sgt,capture_timestamp_sgt,scheduled_slot_sgt,source_date,Gyoha,Gunsan,Mokpo,Suncheon,Ulsan,Jangrim,Chuncheon`. Pressures are recorded in MPa. The source date can be older than the capture date; do not treat four archived copies of one published daily observation as four independent intraday measurements.

**Validation note:** The page's station names, source dates and pressures have been confirmed from its indexed public text, but live HTTP downloading from this development environment was unavailable. Verify one real GitHub Actions run before relying on the archive. Only public data are accessed; do not attempt to bypass access restrictions if KOGAS blocks automated requests.

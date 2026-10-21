#!/usr/bin/env python3
"""Archive the seven publicly displayed KOGAS pipeline pressure readings."""
from __future__ import annotations

import argparse
import csv
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

URL = 'https://www.kogas.or.kr/site/koGas/pressureInfo.do?Key=1040204000000'
SGT = ZoneInfo('Asia/Singapore')
STATIONS = {
    'Gyoha': '교하',
    'Gunsan': '군산',
    'Mokpo': '목포',
    'Suncheon': '순천',
    'Ulsan': '울산',
    'Jangrim': '장림',
    'Chuncheon': '춘천',
}
FIELDS = ['capture_date_sgt', 'capture_time_sgt', 'capture_timestamp_sgt',
          'scheduled_slot_sgt', 'source_date'] + list(STATIONS)


def fetch_html() -> str:
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (compatible; public-KOGAS-pressure-archive/1.0)',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
    })
    last_exception = None
    for attempt in range(1, 5):
        try:
            response = session.get(URL, timeout=35)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or 'utf-8'
            if len(response.content) < 500:
                raise ValueError('Unexpectedly short HTML response')
            return response.text
        except (requests.RequestException, ValueError) as exc:
            last_exception = exc
            logging.warning('Fetch attempt %d/4 failed: %s', attempt, exc)
            if attempt < 4:
                time.sleep(3 * attempt)
    raise RuntimeError(f'Unable to fetch KOGAS page: {last_exception}')


def parse_pressures(html: str) -> tuple[str, dict[str, float]]:
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script', 'style', 'noscript']):
        tag.decompose()
    text = soup.get_text(' ', strip=True)
    text = re.sub(r'\s+', ' ', text)

    # The published page uses: '지역 :교하 ... 날짜 : 2026년10월10일 ... 압력 : 5.489MPa'.
    # Locate each station section first, avoiding unrelated occurrences on the map.
    boundaries = list(re.finditer(r'지역\s*[:：]\s*(' + '|'.join(STATIONS.values()) + r')\b', text))
    by_korean: dict[str, tuple[str, float]] = {}
    for i, match in enumerate(boundaries):
        station_ko = match.group(1)
        end = boundaries[i + 1].start() if i + 1 < len(boundaries) else len(text)
        section = text[match.end():end]
        date = re.search(r'날짜\s*[:：]\s*(20\d{2})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일', section)
        pressure = re.search(r'압력\s*[:：]\s*([\d,.]+)\s*MPa\b', section, re.IGNORECASE)
        if not date or not pressure:
            continue
        date_iso = f'{int(date.group(1)):04d}-{int(date.group(2)):02d}-{int(date.group(3)):02d}'
        value = float(pressure.group(1).replace(',', ''))
        if not 0 < value < 20:
            raise ValueError(f'Implausible pressure for {station_ko}: {value} MPa')
        if station_ko in by_korean and by_korean[station_ko] != (date_iso, value):
            raise ValueError(f'Conflicting measurements for {station_ko}')
        by_korean[station_ko] = (date_iso, value)

    missing = [name for name, korean in STATIONS.items() if korean not in by_korean]
    if missing:
        raise ValueError(f'Missing stations {missing}. Found: {sorted(by_korean)}. Page HTML may have changed.')
    source_dates = {v[0] for v in by_korean.values()}
    if len(source_dates) != 1:
        raise ValueError(f'Mismatched station source dates: {source_dates}')
    source_date = source_dates.pop()
    return source_date, {name: by_korean[korean][1] for name, korean in STATIONS.items()}


def save_row(path: Path, row: dict[str, str | float]) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    prior: list[dict[str, str]] = []
    if path.exists():
        with path.open(newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            if reader.fieldnames != FIELDS:
                raise ValueError(f'Unexpected CSV columns in {path}: {reader.fieldnames}')
            prior = list(reader)

    # Rerunning a scheduled slot updates that slot, instead of writing duplicates.
    # Manual runs use an exact capture timestamp so they remain distinct.
    key = (row['capture_date_sgt'], row['scheduled_slot_sgt'])
    existing = next((i for i, old in enumerate(prior)
                     if (old['capture_date_sgt'], old['scheduled_slot_sgt']) == key
                     and row['scheduled_slot_sgt'] != 'manual'), None)
    if existing is not None:
        prior[existing] = row
        operation = 'updated'
    else:
        prior.append(row)
        operation = 'appended'
    prior.sort(key=lambda item: item['capture_timestamp_sgt'])
    tmp_path = path.with_suffix(path.suffix + '.tmp')
    with tmp_path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(prior)
    tmp_path.replace(path)
    logging.info('%s %s: %s (%s)', operation, path, row['source_date'], row['scheduled_slot_sgt'])
    return operation == 'appended'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('data/kogas_pressures.csv'))
    parser.add_argument('--slot', choices=['07:00', '12:00', '17:00', '22:00', 'manual'], default='manual')
    parser.add_argument('--html-file', type=Path, help='Parse a local saved page instead of downloading')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    now = datetime.now(SGT)
    html = args.html_file.read_text(encoding='utf-8') if args.html_file else fetch_html()
    source_date, readings = parse_pressures(html)
    row = {
        'capture_date_sgt': now.date().isoformat(),
        'capture_time_sgt': now.strftime('%H:%M:%S'),
        'capture_timestamp_sgt': now.isoformat(timespec='seconds'),
        'scheduled_slot_sgt': args.slot,
        'source_date': source_date,
        **readings,
    }
    logging.info('KOGAS source date: %s; recorded at %s', source_date, row['capture_timestamp_sgt'])
    logging.info('Pressures (MPa): %s', readings)
    if source_date != now.date().isoformat():
        logging.warning('Source date %s differs from capture date %s; preserving as published.',
                        source_date, now.date().isoformat())
    save_row(args.output, row)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        logging.error('%s: %s', type(exc).__name__, exc)
        sys.exit(1)

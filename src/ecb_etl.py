from __future__ import annotations
from collections.abc import Mapping, Iterable

import csv
import io
import statistics
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Final
from zipfile import ZipFile

import requests


DAILY_ZIP_URL: Final[str] = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref.zip"
HIST_ZIP_URL: Final[str] = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip"

TARGET_CURRENCIES: Final[tuple[str, ...]] = ("USD", "SEK", "GBP", "JPY")


@dataclass(frozen=True)
class RatesSnapshot:
    as_of: date
    rates: dict[str, float]


def parse_ecb_date(value: str) -> date:
    value_stripped: str = value.strip()

    try:
        return date.fromisoformat(value_stripped)
    except ValueError:
        pass

    return datetime.strptime(value_stripped, "%d %B %Y").date()


def download_zip(url: str, timeout_seconds: int = 30) -> bytes:
    response: requests.Response = requests.get(url, timeout=timeout_seconds)
    response.raise_for_status()
    return response.content


def read_single_file_from_zip(zip_bytes: bytes) -> tuple[str, bytes]:
    with ZipFile(io.BytesIO(zip_bytes)) as zip_file:
        names: list[str] = zip_file.namelist()
        if not names:
            raise ValueError("ZIP contains no files.")

        preferred: tuple[str, ...] = (
            "eurofxref-daily.xml",
            "eurofxref-hist.xml",
            "eurofxref.csv",
            "eurofxref-hist.csv",
        )

        chosen: str | None = next((p for p in preferred if p in names), None)

        if chosen is None:
            data_files: list[str] = [n for n in names if n.lower().endswith((".xml", ".csv"))]
            if not data_files:
                raise ValueError(f"No supported data file found in ZIP. Entries: {names}")
            chosen = data_files[0]

        content: bytes = zip_file.read(chosen)
        return chosen, content


def _parse_ecb_xml(xml_text: str) -> list[RatesSnapshot]:
    root: ET.Element = ET.fromstring(xml_text)
    snapshots: list[RatesSnapshot] = []

    for time_node in root.findall(".//*[@time]"):
        time_str: str | None = time_node.attrib.get("time")
        if time_str is None:
            continue

        as_of: date = parse_ecb_date(time_str)
        rates: dict[str, float] = {}

        for rate_node in time_node.findall("./*[@currency][@rate]"):
            currency: str = rate_node.attrib["currency"]
            rate_str: str = rate_node.attrib["rate"]

            try:
                rate_value: float = float(rate_str)
            except ValueError:
                continue

            rates[currency] = rate_value

        snapshots.append(RatesSnapshot(as_of=as_of, rates=rates))

    snapshots.sort(key=lambda s: s.as_of)
    return snapshots


def _parse_ecb_daily_csv(csv_bytes: bytes) -> RatesSnapshot:
    text: str = csv_bytes.decode("utf-8-sig")
    reader: csv.DictReader[str] = csv.DictReader(io.StringIO(text))

    rows: list[dict[str, str | None]] = list(reader)
    if not rows:
        raise ValueError("Daily CSV has no rows.")

    row: dict[str, str | None] = rows[0]

    date_str: str | None = row.get("Date")
    if not date_str:
        date_str = row.get("DATE")
    if not date_str:
        raise ValueError("Daily CSV missing 'Date' column.")

    as_of: date = parse_ecb_date(date_str)

    rates: dict[str, float] = {}
    for raw_ccy, value in row.items():
        ccy: str = raw_ccy.strip().upper()

        if ccy == "DATE" or value is None or value.strip() == "":
            continue

        try:
            rates[ccy] = float(value)
        except ValueError:
            continue

    return RatesSnapshot(as_of=as_of, rates=rates)


def _parse_ecb_hist_csv(csv_bytes: bytes) -> list[RatesSnapshot]:
    text: str = csv_bytes.decode("utf-8-sig")
    reader: csv.DictReader[str] = csv.DictReader(io.StringIO(text))

    snapshots: list[RatesSnapshot] = []
    for row in reader:
        date_str: str | None = row.get("Date") or row.get("DATE")
        if not date_str:
            continue

        as_of: date = parse_ecb_date(date_str)

        rates: dict[str, float] = {}
        for raw_ccy, value in row.items():
            ccy: str = raw_ccy.strip().upper()

            if ccy == "DATE" or value is None or value.strip() == "":
                continue

            try:
                rates[ccy] = float(value)
            except ValueError:
                continue

        snapshots.append(RatesSnapshot(as_of=as_of, rates=rates))

    snapshots.sort(key=lambda s: s.as_of)
    return snapshots


def load_daily_snapshot() -> RatesSnapshot:
    zip_bytes: bytes = download_zip(DAILY_ZIP_URL)
    filename, payload = read_single_file_from_zip(zip_bytes)

    if filename.lower().endswith(".xml"):
        xml_text: str = payload.decode("utf-8")
        snapshots: list[RatesSnapshot] = _parse_ecb_xml(xml_text)
        if not snapshots:
            raise ValueError("No daily rates found in ECB daily XML.")
        return snapshots[-1]

    if filename.lower().endswith(".csv"):
        return _parse_ecb_daily_csv(payload)

    raise ValueError(f"Unsupported daily file format in ZIP: {filename}")


def load_historical_snapshots() -> list[RatesSnapshot]:
    zip_bytes: bytes = download_zip(HIST_ZIP_URL)
    filename, payload = read_single_file_from_zip(zip_bytes)

    if filename.lower().endswith(".xml"):
        xml_text: str = payload.decode("utf-8")
        snapshots: list[RatesSnapshot] = _parse_ecb_xml(xml_text)
        if not snapshots:
            raise ValueError("No historical rates found in ECB historical XML.")
        return snapshots

    if filename.lower().endswith(".csv"):
        snapshots: list[RatesSnapshot] = _parse_ecb_hist_csv(payload)
        if not snapshots:
            raise ValueError("No historical rates found in ECB historical CSV.")
        return snapshots

    raise ValueError(f"Unsupported historical file format in ZIP: {filename}")


def select_currencies(rates: Mapping[str, float], currencies: Iterable[str]) -> dict[str, float]:
    selected: dict[str, float] = {}
    for ccy in currencies:
        if ccy in rates:
            selected[ccy] = rates[ccy]
    return selected


def compute_historical_means(
    historical: list[RatesSnapshot],
    currencies: Iterable[str],
) -> dict[str, float]:
    buckets: dict[str, list[float]] = {ccy: [] for ccy in currencies}

    for snap in historical:
        for ccy in buckets:
            value: float | None = snap.rates.get(ccy)
            if value is not None:
                buckets[ccy].append(value)

    means: dict[str, float] = {}
    for ccy, values in buckets.items():
        if not values:
            continue
        means[ccy] = float(statistics.fmean(values))

    return means


def render_markdown_table(
    daily: RatesSnapshot,
    means: dict[str, float],
    currencies: Iterable[str],
) -> str:
    lines: list[str] = []
    lines.append("# ECB Exchange Rates (EUR base)\n")
    lines.append(f"**Daily rates date:** {daily.as_of.isoformat()}\n")
    lines.append("| Currency Code | Rate | Mean Historical Rate |")
    lines.append("|---|---:|---:|")

    for ccy in currencies:
        rate: float | None = daily.rates.get(ccy)
        mean: float | None = means.get(ccy)

        rate_cell: str = f"{rate:.6f}" if rate is not None else "N/A"
        mean_cell: str = f"{mean:.6f}" if mean is not None else "N/A"

        lines.append(f"| {ccy} | {rate_cell} | {mean_cell} |")

    lines.append("")
    return "\n".join(lines)


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
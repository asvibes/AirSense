#!/usr/bin/env python3
"""Generate a reproducible AirSense analytics report from synthetic data."""

from __future__ import annotations

import csv
import html
import math
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "database" / "powerbi"
CSV_PATH = OUTPUT_DIR / "airsense-synthetic-readings.csv"
REPORT_PATH = OUTPUT_DIR / "airsense-analytics-report.html"

ROOMS = ("Living Room", "Bedroom", "Kitchen")
METRICS = (
    ("CO2", "ppm"),
    ("TEMPERATURE", "C"),
    ("HUMIDITY", "%"),
)
START = datetime(2026, 1, 1, tzinfo=timezone.utc)
HOURS = 7 * 24
CO2_ANALYSIS_CUTOFF = 1000
COLORS = ("#2463eb", "#0f8b8d", "#d97706")


def build_records() -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    room_offsets = (0, 115, 210)

    for room_index, room in enumerate(ROOMS):
        for hour_index in range(HOURS):
            timestamp = START + timedelta(hours=hour_index)
            hour_of_day = timestamp.hour
            day_index = hour_index // 24
            daytime = max(0.0, math.sin(math.pi * (hour_of_day - 6) / 14))
            weekly = math.sin(2 * math.pi * day_index / 7)
            co2 = (
                610
                + room_offsets[room_index]
                + 260 * daytime
                + 35 * weekly
                + 24 * math.sin(hour_index * 0.73 + room_index)
            )
            temperature = (
                21.3
                + room_index * 0.55
                + 1.8 * math.sin(2 * math.pi * (hour_of_day - 8) / 24)
                + 0.35 * weekly
            )
            humidity = (
                44
                + room_index * 2.5
                + 5.5 * math.sin(2 * math.pi * (hour_of_day + 3) / 24)
                - 1.2 * weekly
            )

            for (metric_code, unit), value in zip(
                METRICS, (co2, temperature, humidity)
            ):
                records.append(
                    {
                        "observed_at_utc": timestamp.isoformat().replace("+00:00", "Z"),
                        "room": room,
                        "metric_code": metric_code,
                        "value": f"{value:.2f}",
                        "unit": unit,
                        "source": "dataset",
                        "dataset_label": "synthetic_demonstration",
                    }
                )

    return records


def write_csv(records: list[dict[str, str]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def read_records() -> list[dict[str, str]]:
    with CSV_PATH.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def summarize(records: list[dict[str, str]]) -> dict[str, object]:
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    daily_co2: dict[tuple[str, str], list[float]] = defaultdict(list)

    for row in records:
        value = float(row["value"])
        grouped[(row["room"], row["metric_code"])].append(value)
        if row["metric_code"] == "CO2":
            day = row["observed_at_utc"][:10]
            daily_co2[(row["room"], day)].append(value)

    co2_values = [
        float(row["value"]) for row in records if row["metric_code"] == "CO2"
    ]
    exceedances = sum(value > CO2_ANALYSIS_CUTOFF for value in co2_values)

    return {
        "grouped": grouped,
        "daily_co2": {
            key: statistics.fmean(values) for key, values in daily_co2.items()
        },
        "co2_values": co2_values,
        "co2_mean": statistics.fmean(co2_values),
        "co2_median": statistics.median(co2_values),
        "co2_min": min(co2_values),
        "co2_max": max(co2_values),
        "co2_exceedances": exceedances,
    }


def line_chart(summary: dict[str, object]) -> str:
    daily_co2 = summary["daily_co2"]
    dates = sorted({day for _, day in daily_co2})
    width, height = 900, 380
    left, right, top, bottom = 76, 26, 34, 58
    min_y, max_y = 500, 1400
    plot_width = width - left - right
    plot_height = height - top - bottom

    def x_position(index: int) -> float:
        return left + plot_width * index / max(1, len(dates) - 1)

    def y_position(value: float) -> float:
        return top + plot_height * (max_y - value) / (max_y - min_y)

    parts = [
        f'<svg role="img" aria-labelledby="co2-title co2-desc" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">',
        '<title id="co2-title">Daily mean synthetic CO2 by room</title>',
        '<desc id="co2-desc">Line chart of seven daily means for three fictional rooms.</desc>',
    ]

    for tick in range(500, 1401, 150):
        y = y_position(tick)
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" stroke="#dbe3ee"/>'
        )
        parts.append(
            f'<text x="{left-12}" y="{y+5:.1f}" text-anchor="end" class="axis">{tick}</text>'
        )

    cutoff_y = y_position(CO2_ANALYSIS_CUTOFF)
    parts.append(
        f'<line x1="{left}" y1="{cutoff_y:.1f}" x2="{width-right}" y2="{cutoff_y:.1f}" stroke="#b45309" stroke-dasharray="7 6"/>'
    )
    parts.append(
        f'<text x="{width-right-4}" y="{cutoff_y-7:.1f}" text-anchor="end" class="cutoff">Illustrative analysis cutoff: {CO2_ANALYSIS_CUTOFF} ppm</text>'
    )

    for index, day in enumerate(dates):
        parts.append(
            f'<text x="{x_position(index):.1f}" y="{height-24}" text-anchor="middle" class="axis">{html.escape(day[5:])}</text>'
        )

    for room_index, room in enumerate(ROOMS):
        points = [
            (
                x_position(index),
                y_position(daily_co2[(room, day)]),
                daily_co2[(room, day)],
                day,
            )
            for index, day in enumerate(dates)
        ]
        point_text = " ".join(f"{x:.1f},{y:.1f}" for x, y, _, _ in points)
        color = COLORS[room_index]
        parts.append(
            f'<polyline points="{point_text}" fill="none" stroke="{color}" stroke-width="3"/>'
        )
        for x, y, value, day in points:
            parts.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="{color}"><title>{escape(room)}, {escape(day)}: {value:.1f} ppm</title></circle>'
            )

    parts.append(
        f'<text x="{left}" y="20" class="axis">Daily mean CO2 (ppm)</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


def room_summary_table(summary: dict[str, object]) -> str:
    grouped = summary["grouped"]
    rows = []
    for room in ROOMS:
        co2 = grouped[(room, "CO2")]
        temp = grouped[(room, "TEMPERATURE")]
        humidity = grouped[(room, "HUMIDITY")]
        over = sum(value > CO2_ANALYSIS_CUTOFF for value in co2)
        rows.append(
            "<tr>"
            f"<th scope=\"row\">{html.escape(room)}</th>"
            f"<td>{statistics.fmean(co2):.1f}</td>"
            f"<td>{min(co2):.1f}–{max(co2):.1f}</td>"
            f"<td>{statistics.fmean(temp):.1f}</td>"
            f"<td>{statistics.fmean(humidity):.1f}</td>"
            f"<td>{over} / {len(co2)} ({100 * over / len(co2):.1f}%)</td>"
            "</tr>"
        )
    return "\n".join(rows)


def daily_summary_table(summary: dict[str, object]) -> str:
    daily_co2 = summary["daily_co2"]
    rows = []
    for day in sorted({day for _, day in daily_co2}):
        cells = [f"<th scope=\"row\">{html.escape(day)}</th>"]
        cells.extend(
            f"<td>{daily_co2[(room, day)]:.1f}</td>" for room in ROOMS
        )
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return "\n".join(rows)


def render_html(records: list[dict[str, str]], summary: dict[str, object]) -> str:
    start = records[0]["observed_at_utc"]
    end = records[-1]["observed_at_utc"]
    co2_count = len(summary["co2_values"])
    exceedance_pct = 100 * summary["co2_exceedances"] / co2_count
    grouped = summary["grouped"]
    temperature_mean = statistics.fmean(
        value for room in ROOMS for value in grouped[(room, "TEMPERATURE")]
    )
    humidity_mean = statistics.fmean(
        value for room in ROOMS for value in grouped[(room, "HUMIDITY")]
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="AirSense descriptive analytics report generated from a clearly labeled synthetic demonstration dataset.">
  <title>AirSense Synthetic Indoor Readings — Analytics Report</title>
  <style>
    :root {{ color-scheme: light; font-family: Segoe UI, Arial, sans-serif; color: #172033; background: #f3f6fa; }}
    body {{ margin: 0; }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 32px 24px 56px; }}
    header {{ border-bottom: 4px solid #2463eb; padding-bottom: 18px; margin-bottom: 24px; }}
    h1 {{ margin: 0 0 8px; font-size: clamp(1.7rem, 3vw, 2.4rem); }}
    h2 {{ margin-top: 34px; }}
    p {{ line-height: 1.55; }}
    .notice {{ border-left: 5px solid #b45309; background: #fff7ed; padding: 14px 18px; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 14px; margin: 20px 0; }}
    .card, .panel {{ background: white; border: 1px solid #dce4ef; border-radius: 10px; padding: 18px; }}
    .card strong {{ display: block; font-size: 1.6rem; margin-top: 6px; }}
    .label {{ color: #526179; font-size: .9rem; }}
    .chart {{ overflow-x: auto; }}
    svg {{ width: 100%; min-width: 660px; height: auto; }}
    .axis {{ fill: #526179; font-size: 13px; }}
    .cutoff {{ fill: #92400e; font-size: 12px; }}
    table {{ width: 100%; border-collapse: collapse; background: white; }}
    th, td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid #dce4ef; }}
    thead th {{ background: #eaf0f8; }}
    .table-wrap {{ overflow-x: auto; border: 1px solid #dce4ef; border-radius: 8px; }}
    code {{ background: #edf2f8; padding: 2px 5px; border-radius: 4px; }}
    footer {{ color: #526179; margin-top: 32px; border-top: 1px solid #dce4ef; padding-top: 16px; }}
    @media print {{ :root {{ background: white; }} main {{ max-width: none; padding: 0; }} .panel, .card {{ break-inside: avoid; }} }}
  </style>
</head>
<body>
<main>
  <header>
    <h1>AirSense Indoor Readings — Analytics Report</h1>
    <p>Descriptive analysis of a reproducible synthetic demonstration dataset</p>
    <p><strong>Observation window:</strong> {html.escape(start)} to {html.escape(end)} · UTC</p>
  </header>

  <section class="notice" aria-label="Dataset notice">
    <strong>Important — synthetic data only.</strong>
    These observations were generated deterministically for an academic report.
    They were not collected from AirSense, a physical sensor, a household, or a public dataset.
    The report is standalone HTML, not a Power BI report or a live data connection.
  </section>

  <section class="cards" aria-label="Summary metrics">
    <article class="card"><span class="label">Observations</span><strong>{len(records):,}</strong><span>3 metrics × 3 rooms × 7 days × 24 hours</span></article>
    <article class="card"><span class="label">Mean CO2</span><strong>{summary["co2_mean"]:.1f} ppm</strong><span>{co2_count} synthetic CO2 samples</span></article>
    <article class="card"><span class="label">Mean temperature</span><strong>{temperature_mean:.1f} °C</strong><span>Across all rooms and timestamps</span></article>
    <article class="card"><span class="label">Mean relative humidity</span><strong>{humidity_mean:.1f}%</strong><span>Across all rooms and timestamps</span></article>
  </section>

  <section class="panel">
    <h2>Daily mean CO2 by room</h2>
    <p>Each point is the arithmetic mean of 24 generated hourly samples for one room and day.</p>
    <div class="chart">{line_chart(summary)}</div>
  </section>

  <section>
    <h2>Room-level summary</h2>
    <div class="table-wrap">
      <table>
        <caption>Summary of synthetic observations by fictional room</caption>
        <thead><tr><th scope="col">Room</th><th scope="col">Mean CO2 (ppm)</th><th scope="col">CO2 min–max (ppm)</th><th scope="col">Mean temperature (°C)</th><th scope="col">Mean humidity (%)</th><th scope="col">Samples above analysis cutoff</th></tr></thead>
        <tbody>{room_summary_table(summary)}</tbody>
      </table>
    </div>
    <p>The cutoff of {CO2_ANALYSIS_CUTOFF} ppm is an illustrative analysis parameter used only to demonstrate aggregation. It is not a health, safety, regulatory, or AirSense alert recommendation.</p>
  </section>

  <section>
    <h2>Daily CO2 means</h2>
    <div class="table-wrap">
      <table>
        <caption>Daily arithmetic mean CO2 by room, ppm</caption>
        <thead><tr><th scope="col">UTC date</th>{''.join(f'<th scope="col">{html.escape(room)}</th>' for room in ROOMS)}</tr></thead>
        <tbody>{daily_summary_table(summary)}</tbody>
      </table>
    </div>
  </section>

  <section class="panel">
    <h2>Method and interpretation</h2>
    <ul>
      <li>The generator creates 168 hourly timestamps from 1–7 January 2026 for each of three fictional rooms and records CO2, temperature, and relative humidity at each timestamp.</li>
      <li>Values are deterministic formulas with room and time-of-day variation; the CSV labels every row with source <code>dataset</code> and dataset label <code>synthetic_demonstration</code>.</li>
      <li>Means are arithmetic means; min/max are observed generated values; exceedance counts compare CO2 samples strictly greater than the illustrative cutoff. No inferential or predictive analysis is performed.</li>
      <li>There are {summary["co2_exceedances"]} of {co2_count} CO2 samples ({exceedance_pct:.1f}%) above that illustrative cutoff. This describes this generated dataset only.</li>
      <li>Reproduce the CSV and this HTML report from the repository root with <code>python tools/generate_analytics_report.py</code>. Run with <code>--check</code> to verify the checked-in outputs match the generator.</li>
    </ul>
  </section>

  <section>
    <h2>Data dictionary</h2>
    <div class="table-wrap">
      <table><thead><tr><th scope="col">Field</th><th scope="col">Meaning</th></tr></thead>
      <tbody>
        <tr><th scope="row">observed_at_utc</th><td>Generated measurement timestamp in UTC ISO-8601.</td></tr>
        <tr><th scope="row">room</th><td>Fictional room label; no real household is represented.</td></tr>
        <tr><th scope="row">metric_code</th><td>AirSense-style metric identifier: CO2, TEMPERATURE, or HUMIDITY.</td></tr>
        <tr><th scope="row">value / unit</th><td>Generated numeric observation and its unit (ppm, C, or %).</td></tr>
        <tr><th scope="row">source</th><td><code>dataset</code>, consistent with the application's source category.</td></tr>
        <tr><th scope="row">dataset_label</th><td><code>synthetic_demonstration</code>, identifying the values as generated.</td></tr>
      </tbody></table>
    </div>
  </section>

  <footer>
    <p>Limitations: no live application/database connection, real or public sensor data, missing-data behavior, calibration, deployment, Power BI model, or user study is represented. Do not use these values to assess an actual indoor environment.</p>
    <p>Companion dataset: <a href="airsense-synthetic-readings.csv">airsense-synthetic-readings.csv</a></p>
  </footer>
</main>
</body>
</html>
"""


def verify_outputs() -> None:
    expected_records = build_records()
    actual_records = read_records()
    if actual_records != expected_records:
        raise SystemExit("Dataset verification failed: CSV does not match generator.")

    if len(actual_records) != 3 * HOURS * len(ROOMS):
        raise SystemExit("Dataset verification failed: unexpected observation count.")
    if {row["source"] for row in actual_records} != {"dataset"}:
        raise SystemExit("Dataset verification failed: unexpected source label.")
    if {row["dataset_label"] for row in actual_records} != {
        "synthetic_demonstration"
    }:
        raise SystemExit("Dataset verification failed: synthetic provenance missing.")

    summary = summarize(actual_records)
    expected_report = render_html(actual_records, summary)
    if not REPORT_PATH.exists() or REPORT_PATH.read_text(encoding="utf-8") != expected_report:
        raise SystemExit("Report verification failed: HTML does not match dataset.")
    if "not a Power BI report" not in expected_report:
        raise SystemExit("Report verification failed: format disclosure missing.")
    print(
        f"Verified {len(actual_records)} synthetic rows, "
        f"{len(summary['co2_values'])} CO2 samples, and report {REPORT_PATH.name}."
    )


def main() -> None:
    records = build_records()
    if "--check" in sys.argv[1:]:
        if not CSV_PATH.exists():
            raise SystemExit(f"Dataset not found: {CSV_PATH}")
        verify_outputs()
        return

    write_csv(records)
    REPORT_PATH.write_text(
        render_html(records, summarize(records)), encoding="utf-8", newline="\n"
    )
    verify_outputs()


if __name__ == "__main__":
    main()

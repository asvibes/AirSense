from collections import defaultdict
from datetime import datetime, timezone
from statistics import median

from app.timestamps import format_utc


PAGE_WIDTH = 612
PAGE_HEIGHT = 792


def build_history_pdf(
    *,
    home_name,
    room_name,
    sensor_name,
    start,
    end,
    metrics,
    rows,
    result_limit_reached=False,
):
    readings = [
        {
            "reading": reading,
            "room": room,
            "metric_name": metric_name,
            "unit": unit,
            "sensor": sensor or "Unassigned sensor",
            "expected_interval": expected_interval,
        }
        for reading, room, metric_name, unit, sensor, expected_interval in rows
    ]
    by_metric = defaultdict(list)
    for row in readings:
        by_metric[row["reading"].metric_code].append(row)
    selected_metrics = metrics or sorted(by_metric)
    pages = []
    pages.append(
        _summary_page(
            home_name,
            room_name,
            sensor_name,
            start,
            end,
            selected_metrics,
            by_metric,
            result_limit_reached,
        )
    )
    for offset in range(14, len(selected_metrics), 22):
        pages.append(
            _statistics_page(selected_metrics[offset : offset + 22], by_metric, offset)
        )
    for metric in selected_metrics:
        if by_metric.get(metric):
            pages.append(_chart_page(metric, by_metric[metric]))
    pages.extend(_readings_pages(readings))
    return _assemble_pdf(pages)


def _summary_page(home, room, sensor, start, end, metrics, by_metric, result_limit_reached):
    page = _Page()
    page.text(48, 738, "AirSense | Historical readings report", 20, bold=True)
    page.text(48, 713, f"Generated {format_utc(datetime.now(timezone.utc))}", 9)
    page.rule(48, 700, 564)
    page.text(48, 674, "Household", 9, bold=True)
    page.text(180, 674, home)
    page.text(48, 652, "Room", 9, bold=True)
    page.text(180, 652, room)
    page.text(48, 630, "Sensor", 9, bold=True)
    page.text(180, 630, sensor)
    page.text(48, 608, "Date range (UTC)", 9, bold=True)
    page.text(180, 608, f"{format_utc(start)} to {format_utc(end)}")
    page.text(48, 586, "Parameters", 9, bold=True)
    metric_label = (
        ", ".join(metrics[:7]) + f", and {len(metrics) - 7} more"
        if len(metrics) > 8
        else ", ".join(metrics)
    )
    page.text(180, 586, metric_label if metrics else "No stored parameters")
    count = sum(len(by_metric.get(metric, [])) for metric in metrics)
    page.text(48, 550, f"Stored readings: {count}", 12, bold=True)
    page.text(48, 525, "Summary statistics", 13, bold=True)
    y = 501
    page.text(48, y, "Parameter", 9, bold=True)
    page.text(150, y, "Unit", 9, bold=True)
    page.text(205, y, "Samples", 9, bold=True)
    page.text(290, y, "Minimum", 9, bold=True)
    page.text(380, y, "Average", 9, bold=True)
    page.text(470, y, "Maximum", 9, bold=True)
    page.rule(48, y - 6, 564)
    y -= 25
    for metric in metrics[:14]:
        items = by_metric.get(metric, [])
        values = [float(item["reading"].value) for item in items]
        if values:
            page.text(48, y, metric)
            page.text(150, y, items[0]["unit"])
            page.text(205, y, str(len(values)))
            page.text(290, y, _number(min(values)))
            page.text(380, y, _number(sum(values) / len(values)))
            page.text(470, y, _number(max(values)))
        else:
            page.text(48, y, metric)
            page.text(205, y, "0")
            page.text(290, y, "—")
            page.text(380, y, "—")
            page.text(470, y, "—")
        y -= 22
    page.text(
        48,
        92,
        "Charts show recorded samples only. No missing values are filled or interpolated.",
        9,
    )
    page.text(
        48,
        75,
        "Intervals are calculated from adjacent stored timestamps for the same parameter.",
        9,
    )
    if result_limit_reached:
        page.text(48, 57, "Result limit reached: this report may not contain every matching reading.", 9)
    return page


def _statistics_page(metrics, by_metric, offset):
    page = _Page()
    page.text(48, 738, "Summary statistics | continued", 18, bold=True)
    page.text(48, 714, f"Parameters {offset + 1}–{offset + len(metrics)}", 9)
    headers = [
        (48, "Parameter"),
        (150, "Unit"),
        (205, "Samples"),
        (290, "Minimum"),
        (380, "Average"),
        (470, "Maximum"),
    ]
    for x, label in headers:
        page.text(x, 687, label, 9, bold=True)
    page.rule(48, 679, 564)
    y = 658
    for metric in metrics:
        items = by_metric.get(metric, [])
        values = [float(item["reading"].value) for item in items]
        page.text(48, y, metric)
        if values:
            page.text(150, y, items[0]["unit"])
            page.text(205, y, str(len(values)))
            page.text(290, y, _number(min(values)))
            page.text(380, y, _number(sum(values) / len(values)))
            page.text(470, y, _number(max(values)))
        else:
            page.text(205, y, "0")
            page.text(290, y, "—")
            page.text(380, y, "—")
            page.text(470, y, "—")
        y -= 22
    return page


def _chart_page(metric, items):
    page = _Page()
    page.text(48, 738, f"Historical chart | {metric}", 18, bold=True)
    unit = items[0]["unit"]
    page.text(48, 714, f"Stored samples only · {unit}", 9)
    left, right, bottom, top = 72, 560, 145, 675
    page.rule(left, bottom, right)
    page.line(left, bottom, left, top)
    times = [item["reading"].measured_at.timestamp() for item in items]
    values = [float(item["reading"].value) for item in items]
    start_time, end_time = min(times), max(times)
    low, high = min(values), max(values)
    if low == high:
        low -= max(abs(low) * 0.05, 1)
        high += max(abs(high) * 0.05, 1)
    for fraction in (0, 0.25, 0.5, 0.75, 1):
        y = bottom + fraction * (top - bottom)
        page.line(left, y, right, y, gray=0.82)
        page.text(44, y - 3, _number(low + fraction * (high - low)), 7)
    series = defaultdict(list)
    for item in items:
        reading = item["reading"]
        series[(reading.sensor_id or "unassigned", reading.room_id)].append(item)
    intervals = [
        (current["reading"].measured_at - previous["reading"].measured_at).total_seconds()
        for readings in series.values()
        for previous, current in zip(
            sorted(readings, key=lambda row: row["reading"].measured_at),
            sorted(readings, key=lambda row: row["reading"].measured_at)[1:],
        )
    ]
    median_interval = median(intervals) if intervals else None
    if median_interval:
        for readings in series.values():
            ordered = sorted(readings, key=lambda row: row["reading"].measured_at)
            expected_interval = ordered[0]["expected_interval"]
            if not expected_interval:
                continue
            for previous, current in zip(ordered, ordered[1:]):
                previous_reading = previous["reading"]
                current_reading = current["reading"]
                delta = (current_reading.measured_at - previous_reading.measured_at).total_seconds()
                if delta <= expected_interval * 2:
                    continue
                x1 = left + (previous_reading.measured_at.timestamp() - start_time) / max(end_time - start_time, 1) * (right - left)
                x2 = left + (current_reading.measured_at.timestamp() - start_time) / max(end_time - start_time, 1) * (right - left)
                page.fill_rect(x1, bottom, max(1, x2 - x1), top - bottom)
    for timestamp, value in zip(times, values):
        x_fraction = (timestamp - start_time) / (end_time - start_time) if end_time > start_time else 0.5
        x = left + x_fraction * (right - left)
        y = bottom + (value - low) / (high - low) * (top - bottom)
        page.dot(x, y, 2.2)
    page.text(left, 122, format_utc(items[0]["reading"].measured_at), 8)
    page.text(right - 115, 122, format_utc(items[-1]["reading"].measured_at), 8)
    page.text(48, 90, f"{len(items)} readings · median sampling interval {_duration(median_interval) if median_interval is not None else 'not available'}", 9)
    page.text(48, 72, "Dots are stored samples only; shaded bands exceed configured sensor cadence by 2x.", 9)
    return page


def _readings_pages(readings):
    if not readings:
        page = _Page()
        page.text(48, 738, "Timestamped readings", 18, bold=True)
        page.text(48, 710, "No stored readings matched the selected filters.", 10)
        return [page]

    ordered = sorted(
        readings,
        key=lambda item: (
            item["reading"].measured_at,
            item["reading"].id,
        ),
    )
    previous = {}
    enriched = []
    for item in ordered:
        reading = item["reading"]
        key = (reading.metric_code, reading.sensor_id, reading.room_id)
        prior = previous.get(key)
        interval = (
            (reading.measured_at - prior).total_seconds()
            if prior is not None
            else None
        )
        previous[key] = reading.measured_at
        enriched.append((item, interval))

    pages = []
    chunk_size = 34
    for offset in range(0, len(enriched), chunk_size):
        page = _Page()
        page.text(48, 738, "Timestamped readings", 18, bold=True)
        page.text(48, 714, f"Rows {offset + 1}–{min(offset + chunk_size, len(enriched))} of {len(enriched)}", 9)
        columns = [
            (48, "Timestamp (UTC)"),
            (190, "Room / sensor"),
            (315, "Parameter"),
            (405, "Value"),
            (455, "Unit"),
            (495, "Interval"),
            (548, "Source"),
        ]
        for x, label in columns:
            page.text(x, 687, label, 7, bold=True)
        page.rule(48, 679, 564)
        y = 660
        for item, interval in enriched[offset : offset + chunk_size]:
            reading = item["reading"]
            page.text(48, y, format_utc(reading.measured_at), 6.5)
            page.text(190, y, _fit(f"{item['room']} / {item['sensor']}", 24), 6.5)
            page.text(315, y, _fit(reading.metric_code, 16), 6.5)
            page.text(405, y, _value(reading.value), 6.5)
            page.text(455, y, _fit(item["unit"], 8), 6.5)
            page.text(495, y, _duration(interval) if interval is not None else "—", 6.5)
            page.text(548, y, _fit(reading.source, 8), 6.5)
            y -= 17
        pages.append(page)
    return pages


def _intervals(items):
    ordered = sorted(items, key=lambda item: item["reading"].measured_at)
    return [
        (current["reading"].measured_at - previous["reading"].measured_at).total_seconds()
        for previous, current in zip(ordered, ordered[1:])
    ]


def _duration(seconds):
    seconds = int(round(seconds))
    if seconds < 60:
        return f"{seconds}s"
    minutes, remaining = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {remaining}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"


def _number(value):
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _value(value):
    return format(float(value), ".15g")


def _fit(value, length):
    text = str(value)
    return text if len(text) <= length else text[: length - 1] + "…"


class _Page:
    def __init__(self):
        self.commands = []

    def text(self, x, y, value, size=10, bold=False):
        font = "F2" if bold else "F1"
        self.commands.append(
            f"BT /{font} {size} Tf 1 0 0 1 {x:.2f} {y:.2f} Tm ({_literal(value)}) Tj ET"
        )

    def rule(self, x1, y, x2):
        self.line(x1, y, x2, y)

    def line(self, x1, y1, x2, y2, gray=0.35):
        self.commands.append(
            f"{gray:.2f} G {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S 0 G"
        )

    def dot(self, x, y, radius):
        c = radius * 0.55228475
        self.commands.append(
            f"0.20 0.58 0.49 rg "
            f"{x + radius:.2f} {y:.2f} m "
            f"{x + radius:.2f} {y + c:.2f} {x + c:.2f} {y + radius:.2f} {x:.2f} {y + radius:.2f} c "
            f"{x - c:.2f} {y + radius:.2f} {x - radius:.2f} {y + c:.2f} {x - radius:.2f} {y:.2f} c "
            f"{x - radius:.2f} {y - c:.2f} {x - c:.2f} {y - radius:.2f} {x:.2f} {y - radius:.2f} c "
            f"{x + c:.2f} {y - radius:.2f} {x + radius:.2f} {y - c:.2f} {x + radius:.2f} {y:.2f} c f 0 g"
        )

    def fill_rect(self, x, y, width, height):
        self.commands.append(
            f"0.96 0.88 0.70 rg {x:.2f} {y:.2f} {width:.2f} {height:.2f} re f 0 g"
        )

    def render(self, page_number, total_pages):
        self.text(48, 32, f"AirSense · Historical readings · Page {page_number} of {total_pages}", 8)
        return "\n".join(self.commands).encode("ascii")


def _literal(value):
    text = str(value).replace("—", "-").replace("·", "|").replace("–", "-")
    encoded = text.encode("cp1252", "replace")
    pieces = []
    for byte in encoded:
        if byte in (40, 41, 92):
            pieces.append("\\" + chr(byte))
        elif byte < 32 or byte > 126:
            pieces.append(f"\\{byte:03o}")
        else:
            pieces.append(chr(byte))
    return "".join(pieces)


def _assemble_pdf(pages):
    total = len(pages)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids ["
        + b" ".join(f"{5 + index * 2} 0 R".encode("ascii") for index in range(total))
        + f"] /Count {total} >>".encode("ascii"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
    ]
    for index, page in enumerate(pages, start=1):
        page_object = 5 + (index - 1) * 2
        content_object = page_object + 1
        content = page.render(index, total)
        objects.extend(
            [
                (
                    f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
                    f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> "
                    f"/Contents {content_object} 0 R >>"
                ).encode("ascii"),
                f"<< /Length {len(content)} >>\nstream\n".encode("ascii")
                + content
                + b"\nendstream",
            ]
        )
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode("ascii"))
        output.extend(body)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(output)

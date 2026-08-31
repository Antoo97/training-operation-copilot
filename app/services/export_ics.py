from __future__ import annotations

from datetime import date, timedelta


def esc(value) -> str:
    return str(value or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def calendar(events: list[dict]) -> str:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Training Copilot//ZH-CN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH"]
    for event in events:
        start: date = event["start"]
        end: date = event.get("end") or start
        lines += ["BEGIN:VEVENT", f"UID:{esc(event['uid'])}@training-copilot", f"DTSTART;VALUE=DATE:{start:%Y%m%d}", f"DTEND;VALUE=DATE:{end + timedelta(days=1):%Y%m%d}", f"SUMMARY:{esc(event['summary'])}", f"DESCRIPTION:{esc(event.get('description'))}", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"

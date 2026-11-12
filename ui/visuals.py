"""Small escaped HTML primitives for the reference dashboard; no backend actions."""
from html import escape


ICONS = {
    "code": '<path d="m8 5-6 7 6 7m8-14 6 7-6 7m-3-17-2 20"/>',
    "bug": '<path d="M8 8h8v8a4 4 0 0 1-8 0V8Zm2 0V5h4v3M4 10h4m8 0h4M4 15h4m8 0h4M6 20l3-3m6 0 3 3M5 5l3 3m8 0 3-3M12 9v10"/>',
    "check": '<circle cx="12" cy="12" r="9"/><path d="m7 12 3 3 7-7"/>',
    "shield": '<path d="m12 2 9 4v6c0 5-9 10-9 10S3 17 3 12V6l9-4Z"/><path d="m8 11 3 3 5-5"/>',
    "clock": '<circle cx="12" cy="13" r="9"/><path d="M12 8v6h4M9 1h6M12 1v3"/>',
    "branch": '<circle cx="6" cy="5" r="2"/><circle cx="6" cy="19" r="2"/><circle cx="18" cy="5" r="2"/><path d="M6 7v10m12-10c0 7-12 3-12 10"/>',
    "flask": '<path d="M9 2h6m-5 0v7l-6 10c-1 2 0 3 2 3h12c2 0 3-1 2-3L14 9V2M7 15h10M10 18h4"/>',
    "file": '<path d="M5 2h10l4 4v16H5V2Zm9 0v5h5M8 11h8M8 15h8M8 19h5"/>',
}


def icon(name, size=22):
    return f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS.get(name, ICONS["code"])}</svg>'


def text(value, fallback="Unavailable"):
    return escape(str(value)) if value is not None and value != "" else fallback


def badge(value, tone="muted"):
    return f'<span class="status-badge {tone}">{text(value)}</span>'


def title(label, symbol="file"):
    return f'<div class="panel-heading">{icon(symbol, 16)}<span>{escape(label)}</span></div>'


def row(label, value):
    return f'<div class="evidence-row"><span>{escape(label)}</span><b>{text(value)}</b></div>'


def status_tone(status):
    return "good" if status in ("APPROVE", "approved", "passed", "awaiting_approval") else "bad" if status in ("REJECT", "failed", "error", "rejected") else "muted"


def patch_counts(diff):
    if not isinstance(diff, str) or not diff.strip():
        return None
    lines = diff.splitlines()
    return (sum(line.startswith("+") and not line.startswith("+++") for line in lines),
            sum(line.startswith("-") and not line.startswith("---") for line in lines))

"""Telegram alerting."""
import os
import requests


def send_telegram(text: str, parse_mode: str = "Markdown") -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[notify] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set - skipping alert")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(url, data={
            "chat_id": chat_id, "text": text, "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }, timeout=15)
        if r.status_code != 200:
            print(f"[notify] Telegram send failed: {r.status_code} {r.text}")
            return False
        return True
    except Exception as e:
        print(f"[notify] Telegram send error: {e}")
        return False


def format_alert(row: dict) -> str:
    stage_emoji = {
        "PRE_BOS2_READY": "🟡",
        "FRESH_REVERSAL": "🟠",
        "FRESH_BOS2": "🟢",
        "STALE_BOS2": "⚪",
        "BASING": "🔵",
        "IN_RETEST": "🔵",
    }.get(row["stage"], "⚫")

    lines = [
        f"{stage_emoji} *{row['symbol']}* — `{row['stage']}`",
        f"Close: {row['last_close']}  ({row['last_date']})",
        f"P0(base): {row.get('P0_base_level')}   P1(resistance): {row.get('P1_resistance')}",
    ]
    if row["stage"] == "PRE_BOS2_READY":
        lines.append(f"Distance to breakout: {row.get('distance_to_p1_pct')}%")
        lines.append(f"Volatility contracted: {row.get('volatility_contracted')}")
    if row["stage"] == "FRESH_REVERSAL":
        lines.append(f"Reversal entry: {row.get('Reversal_date')} @ {row.get('Reversal_price')}")
        lines.append(f"Distance to full breakout (P1): {row.get('distance_to_p1_pct')}%")
    if row.get("BOS2_date"):
        lines.append(f"BOS2: {row['BOS2_date']} @ {row['BOS2_price']} ({row.get('bars_since_bos2')} bars ago)")
    lines.append(f"Confluence: {row.get('confluence_score')}")
    lines.append(f"_{row.get('notes','')}_")
    return "\n".join(lines)


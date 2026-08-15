#!/usr/bin/env python3
"""
TFT Patch Watcher
------------------
Tải dữ liệu TFT mới nhất từ Community Dragon, so sánh với snapshot lần
trước, và gửi cảnh báo Discord nếu có thay đổi (champion, trait, item,
augment...). Snapshot được lưu trong data/ để Git tự làm "database"
version-controlled.

Chạy: python scripts/fetch_and_diff.py
Biến môi trường tuỳ chọn:
  DISCORD_WEBHOOK_URL - webhook Discord để gửi cảnh báo
  CDRAGON_REGION      - "latest" (mặc định, theo live) hoặc "pbe"
"""

import json
import os
import sys
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import urllib.request
import urllib.error

REGION = os.environ.get("CDRAGON_REGION", "latest")  # "latest" hoặc "pbe"
SOURCE_URL = f"https://raw.communitydragon.org/{REGION}/cdragon/tft/en_us.json"

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SNAPSHOT_PATH = DATA_DIR / "last_snapshot.json"
DIFF_LOG_PATH = DATA_DIR / "diff_log.jsonl"

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()

# ----------------------------------------------------------------------
# Fetch
# ----------------------------------------------------------------------

def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "tft-patch-watcher/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
    except urllib.error.URLError as e:
        print(f"[ERROR] Không thể tải dữ liệu từ {url}: {e}", file=sys.stderr)
        sys.exit(1)
    return json.loads(raw)


# ----------------------------------------------------------------------
# Chuẩn hoá dữ liệu: chỉ giữ các trường quan trọng để so sánh
# (tránh nhiễu do metadata không liên quan tới balance thay đổi)
# ----------------------------------------------------------------------

def normalize(data: dict) -> dict:
    """Trích các set đang active + item/augment, giữ field liên quan tới balance."""
    out = {"champions": {}, "traits": {}, "items": {}}

    # Cấu trúc CDragon: data["setData"] là list các set (thường chỉ 1-2 set active)
    for set_entry in data.get("setData", []):
        set_number = set_entry.get("number")
        for champ in set_entry.get("champions", []):
            key = f"set{set_number}:{champ.get('apiName')}"
            out["champions"][key] = {
                "name": champ.get("name"),
                "cost": champ.get("cost"),
                "stats": champ.get("stats"),
                "traits": champ.get("traits"),
                "ability": {
                    "name": (champ.get("ability") or {}).get("name"),
                    "desc": (champ.get("ability") or {}).get("desc"),
                    "variables": (champ.get("ability") or {}).get("variables"),
                },
            }
        for trait in set_entry.get("traits", []):
            key = f"set{set_number}:{trait.get('apiName')}"
            out["traits"][key] = {
                "name": trait.get("name"),
                "effects": trait.get("effects"),
            }

    for item in data.get("items", []):
        key = item.get("apiName")
        if not key:
            continue
        out["items"][key] = {
            "name": item.get("name"),
            "desc": item.get("desc"),
            "effects": item.get("effects"),
        }

    return out


def sha256_of(obj) -> str:
    blob = json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


# ----------------------------------------------------------------------
# Diff
# ----------------------------------------------------------------------

def diff_section(old: dict, new: dict) -> dict:
    """So sánh 2 dict cùng cấu trúc {key: {field: value}}."""
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = {}
    for key in set(old) & set(new):
        if old[key] != new[key]:
            changed[key] = {"before": old[key], "after": new[key]}
    return {"added": added, "removed": removed, "changed": changed}


def build_diff(old: dict, new: dict) -> dict:
    return {
        "champions": diff_section(old.get("champions", {}), new.get("champions", {})),
        "traits": diff_section(old.get("traits", {}), new.get("traits", {})),
        "items": diff_section(old.get("items", {}), new.get("items", {})),
    }


def diff_is_empty(diff: dict) -> bool:
    for section in diff.values():
        if section["added"] or section["removed"] or section["changed"]:
            return False
    return True


def summarize_diff(diff: dict, max_items: int = 15) -> str:
    lines = []
    for section_name, section in diff.items():
        parts = []
        if section["added"]:
            parts.append(f"+{len(section['added'])} mới")
        if section["removed"]:
            parts.append(f"-{len(section['removed'])} bị xoá")
        if section["changed"]:
            parts.append(f"~{len(section['changed'])} thay đổi")
        if parts:
            lines.append(f"**{section_name}**: " + ", ".join(parts))
            # liệt kê chi tiết vài mục thay đổi
            shown = 0
            for key in section["changed"]:
                if shown >= max_items:
                    lines.append(f"  ...và {len(section['changed']) - shown} thay đổi khác")
                    break
                lines.append(f"  • `{key}` thay đổi")
                shown += 1
    return "\n".join(lines) if lines else "Không có thay đổi."


# ----------------------------------------------------------------------
# Discord alert
# ----------------------------------------------------------------------

def send_discord_alert(summary: str, patch_region: str):
    if not DISCORD_WEBHOOK_URL:
        print("[INFO] Chưa cấu hình DISCORD_WEBHOOK_URL, bỏ qua gửi cảnh báo.")
        return

    content = f"🔔 **TFT Patch Watcher** phát hiện thay đổi dữ liệu ({patch_region})\n\n{summary}"
    # Discord giới hạn 2000 ký tự / message
    content = content[:1900] + ("\n...(cắt bớt)" if len(content) > 1900 else "")

    payload = json.dumps({"content": content}).encode("utf-8")
    req = urllib.request.Request(
        DISCORD_WEBHOOK_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"[INFO] Đã gửi Discord webhook, status={resp.status}")
    except urllib.error.URLError as e:
        print(f"[ERROR] Gửi Discord webhook thất bại: {e}", file=sys.stderr)


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] Đang tải dữ liệu từ {SOURCE_URL} ...")
    raw = fetch_json(SOURCE_URL)
    new_snapshot = normalize(raw)
    new_hash = sha256_of(new_snapshot)

    if SNAPSHOT_PATH.exists():
        old_snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    else:
        old_snapshot = {"champions": {}, "traits": {}, "items": {}}
        print("[INFO] Chưa có snapshot trước đó, đây là lần chạy đầu tiên.")

    diff = build_diff(old_snapshot, new_snapshot)

    if diff_is_empty(diff):
        print("[INFO] Không có thay đổi so với lần trước.")
    else:
        summary = summarize_diff(diff)
        print("[INFO] Phát hiện thay đổi:\n" + summary)

        # Ghi log diff (append, dạng jsonl để dễ theo dõi lịch sử)
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "region": REGION,
            "hash": new_hash,
            "diff": diff,
        }
        with DIFF_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

        send_discord_alert(summary, REGION)

    # Luôn ghi đè snapshot mới nhất (để lần chạy sau so sánh)
    SNAPSHOT_PATH.write_text(
        json.dumps(new_snapshot, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    print(f"[INFO] Đã lưu snapshot mới, hash={new_hash[:12]}...")


if __name__ == "__main__":
    main()

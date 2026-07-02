#!/usr/bin/env python3
"""Keygen tool for Olga English Coach license keys (Level 2).

Generates license keys in format: OLGA-XXXX-XXXX-XXXX-XXXX

Modes:
    - Email-only key: works on any machine (legacy / universal)
    - Machine-bound key: tied to one specific device

Usage:
    python3 keygen.py customer@email.com
    python3 keygen.py customer@email.com <machine_id>
    python3 keygen.py --file customers.txt
    python3 keygen.py --file customers.txt --bound

The algorithm must match license_manager.py exactly.
"""

from __future__ import annotations

import argparse
import hashlib
import sys


# Secret key components — assembled at runtime to avoid plaintext in binary
_S1 = b"\x4f\x6c\x67\x61\x45\x6e\x67"  # "OlgaEng"
_S2 = b"\x6c\x69\x73\x68\x43\x6f\x61"  # "lishCoa"
_S3 = b"\x63\x68\x32\x30\x32\x34\x5f"  # "ch2024_"
_S4 = b"\x48\x6d\x61\x63\x53\x65\x63"  # "HmacSec"
_S5 = b"\x72\x65\x74\x4b\x65\x79"      # "retKey"
_S6 = b"\x5f\x76\x31"                   # "_v1"


def _get_secret() -> bytes:
    return _S1 + _S2 + _S3 + _S4 + _S5 + _S6


_LICENSE_SECRET = _get_secret()


def generate_key(email: str, machine_id: str = "") -> str:
    """Generate a license key from customer email and optional machine_id.

    If machine_id is empty, the key is universal (works on any machine).
    If machine_id is provided, the key is bound to that device.
    """
    base = _LICENSE_SECRET + email.strip().lower().encode()
    if machine_id:
        base += b"\x00" + machine_id.strip().encode()
    h = hashlib.sha256(base).hexdigest()
    key_part = h[:16].upper()
    return f"OLGA-{key_part[:4]}-{key_part[4:8]}-{key_part[8:12]}-{key_part[12:16]}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Olga English Coach license keys",
    )
    parser.add_argument(
        "email",
        nargs="?",
        help="Customer email",
    )
    parser.add_argument(
        "machine_id",
        nargs="?",
        help="Optional machine ID for device-bound key",
    )
    parser.add_argument(
        "--file", "-f",
        metavar="PATH",
        help="File with one email per line (optional machine_id after comma)",
    )
    parser.add_argument(
        "--csv", "-c",
        action="store_true",
        help="Output CSV format: email,machine_id,key",
    )
    args = parser.parse_args()

    rows: list[tuple[str, str, str]] = []

    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split(",")
                    email = parts[0].strip()
                    mid = parts[1].strip() if len(parts) > 1 else ""
                    rows.append((email, mid, generate_key(email, mid)))
        except FileNotFoundError:
            print(f"Error: file not found: {args.file}")
            return 1
    elif args.email:
        rows.append((args.email, args.machine_id or "", generate_key(args.email, args.machine_id or "")))
    else:
        parser.print_help()
        return 1

    if args.csv:
        print("email,machine_id,key")
        for email, mid, key in rows:
            print(f"{email},{mid},{key}")
    else:
        print(f"{'Email':<40} {'Machine ID':<40} {'License Key'}")
        print("-" * 95)
        for email, mid, key in rows:
            print(f"{email:<40} {mid if mid else '-':<40} {key}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

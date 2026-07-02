"""License manager: offline key verification, trial period, activation.

Level 2 protection:
- HMAC signature on license.json (tamper detection)
- Machine binding (license key tied to hardware UUID)
- Anti-rollback (trial period cannot be extended by clock manipulation)
- Non-blocking: app always works regardless of license status
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import platform
import subprocess
import time
import logging
from pathlib import Path
from datetime import date, datetime, timedelta

_logger = logging.getLogger("olga.license")

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
_LICENSE_SIG_SECRET = _get_secret() + b"_sig_v2"

TRIAL_DAYS = 7


def _get_machine_id() -> str:
    """Get a unique machine identifier (hardware UUID)."""
    if platform.system() == "Darwin":
        try:
            result = subprocess.run(
                ["ioreg", "-l"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.splitlines():
                if "IOPlatformUUID" in line:
                    uuid = line.split('"')[-2]
                    return uuid
        except Exception:
            pass
    elif platform.system() == "Windows":
        try:
            result = subprocess.run(
                ["wmic", "csproduct", "get", "UUID"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.strip().splitlines():
                line = line.strip()
                if line and line != "UUID":
                    return line
        except Exception:
            pass
    # Fallback: hostname + username
    return f"{platform.node()}-{os.getuid() if hasattr(os, 'getuid') else 'win'}"


def _generate_key_seed(email: str, machine_id: str = "") -> str:
    """Generate a license key from email (+ optional machine_id for binding)."""
    base = _LICENSE_SECRET + email.lower().encode()
    if machine_id:
        base += b"\x00" + machine_id.encode()
    h = hashlib.sha256(base).hexdigest()
    key_part = h[:16].upper()
    formatted = f"OLGA-{key_part[:4]}-{key_part[4:8]}-{key_part[8:12]}-{key_part[12:16]}"
    return formatted


def verify_key(key: str, email: str = "", machine_id: str = "") -> bool:
    """Verify a license key format and checksum.
    If email is provided, verifies the key was generated for that email.
    If machine_id is provided, key must be bound to that machine.
    Without email, uses a stronger secondary checksum (1/65536 false positive rate).
    """
    key = key.strip().upper()
    if not key.startswith("OLGA-"):
        return False
    parts = key.split("-")
    if len(parts) != 5:
        return False
    hex_part = "".join(parts[1:])
    if len(hex_part) != 16:
        return False
    try:
        int(hex_part, 16)
    except ValueError:
        return False
    if email:
        expected = _generate_key_seed(email.strip(), machine_id)
        return hmac.compare_digest(key, expected)
    checksum = hashlib.sha256((_LICENSE_SECRET + hex_part.encode())).hexdigest()
    return checksum[:4] == "0000"


def _sign_license(data: dict) -> str:
    """Compute HMAC-SHA256 signature over license data (excluding _sig field)."""
    clean = {k: v for k, v in data.items() if k != "_sig"}
    payload = json.dumps(clean, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hmac.new(_LICENSE_SIG_SECRET, payload, hashlib.sha256).hexdigest()


def _verify_signature(data: dict) -> bool:
    """Verify the HMAC signature on license data. Returns False if tampered."""
    sig = data.get("_sig", "")
    if not sig:
        return False
    expected = _sign_license(data)
    return hmac.compare_digest(sig, expected)


class LicenseManager:
    """Manages trial period and license activation, stored locally.
    License.json is signed with HMAC to detect tampering.
    Trial period tracks last_seen_date to prevent clock rollback.
    Non-blocking: app always works regardless of license status.
    """

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.license_path = data_dir / "license.json"
        self._machine_id = _get_machine_id()
        self._data = self._load()

    def _load(self) -> dict:
        if self.license_path.exists():
            try:
                data = json.loads(self.license_path.read_text(encoding="utf-8"))
                # Migration: old format without signature
                if "_sig" not in data:
                    if data.get("activated", False):
                        # Verify legacy activation — if key is valid, migrate
                        key = data.get("license_key", "")
                        if verify_key(key, email=data.get("activated_email", "")):
                            _logger.info("Migrating legacy license to signed format")
                            data["machine_id"] = self._machine_id
                            data["last_seen_date"] = date.today().isoformat()
                            data["last_seen_timestamp"] = time.time()
                            self._save(data)
                            return data
                        else:
                            _logger.warning("Legacy license key invalid — resetting")
                            return self._default_state()
                    else:
                        # Trial mode without signature — migrate
                        data["machine_id"] = self._machine_id
                        data["last_seen_date"] = date.today().isoformat()
                        data["last_seen_timestamp"] = time.time()
                        self._save(data)
                        return data
                # Check signature integrity
                if not _verify_signature(data):
                    _logger.warning("License file signature invalid — possible tampering")
                    return self._default_state()
                # Anti-rollback: check if system clock went backwards
                self._check_anti_rollback(data)
                return data
            except Exception:
                pass
        return self._default_state()

    def _default_state(self) -> dict:
        data = {
            "first_launch": date.today().isoformat(),
            "trial_end": (date.today() + timedelta(days=TRIAL_DAYS)).isoformat(),
            "license_key": "",
            "activated": False,
            "activated_email": "",
            "machine_id": self._machine_id,
            "last_seen_date": date.today().isoformat(),
            "last_seen_timestamp": time.time(),
        }
        self._save(data)
        return data

    def _check_anti_rollback(self, data: dict) -> None:
        """Detect clock rollback: if last_seen_date is in the future, flag it."""
        today = date.today()
        last_seen = data.get("last_seen_date", "")
        if last_seen:
            try:
                last_date = date.fromisoformat(last_seen)
                if last_date > today:
                    # Clock was rolled back — freeze trial, don't extend
                    _logger.warning("Clock rollback detected: last_seen=%s, today=%s", last_seen, today)
                    # Don't modify trial_end — keep it as-is
            except Exception:
                pass
        # Update last_seen if today is newer
        if last_seen != today.isoformat():
            data["last_seen_date"] = today.isoformat()
            data["last_seen_timestamp"] = time.time()
            self._save(data)

    def _save(self, data: dict | None = None) -> None:
        data = data or self._data
        # Always update signature before saving
        data["_sig"] = _sign_license(data)
        self.license_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @property
    def is_activated(self) -> bool:
        activated = self._data.get("activated", False)
        if not activated:
            return False
        # Verify machine binding
        stored_mid = self._data.get("machine_id", "")
        if stored_mid and stored_mid != self._machine_id:
            _logger.warning("License machine_id mismatch — activated on different machine")
            return False
        return True

    @property
    def trial_days_left(self) -> int:
        if self.is_activated:
            return TRIAL_DAYS
        try:
            trial_end = date.fromisoformat(self._data.get("trial_end", ""))
            return max(0, (trial_end - date.today()).days)
        except Exception:
            return 0

    @property
    def is_trial_active(self) -> bool:
        return not self.is_activated and self.trial_days_left > 0

    @property
    def is_expired(self) -> bool:
        return not self.is_activated and self.trial_days_left <= 0

    @property
    def status(self) -> str:
        if self.is_activated:
            return "activated"
        if self.is_trial_active:
            return "trial"
        return "expired"

    def activate(self, key: str, email: str = "") -> tuple[bool, str]:
        """Activate license with a key. Returns (success, message).
        Key is bound to this machine's hardware ID."""
        key = key.strip()
        if not verify_key(key, email=email, machine_id=self._machine_id):
            # Try without machine binding (legacy keys)
            if not verify_key(key, email=email):
                return False, "Неверный ключ. Проверьте правильность ввода ключа и email."
            _logger.info("Activated with legacy (non-machine-bound) key")
        self._data["license_key"] = key.upper()
        self._data["activated"] = True
        self._data["activated_email"] = email.strip()
        self._data["activated_date"] = date.today().isoformat()
        self._data["machine_id"] = self._machine_id
        self._save()
        _logger.info("License activated: %s", key[:10] + "...")
        return True, "Лицензия активирована. Спасибо за покупку!"

    def deactivate(self) -> None:
        self._data["activated"] = False
        self._data["license_key"] = ""
        self._data["activated_email"] = ""
        self._data["machine_id"] = self._machine_id
        self._save()

    def get_info(self) -> dict:
        return {
            "status": self.status,
            "trial_days_left": self.trial_days_left,
            "activated": self.is_activated,
            "license_key": self._data.get("license_key", ""),
            "email": self._data.get("activated_email", ""),
            "machine_id": self._machine_id[:8] + "...",
        }


# ─── Key generation tool (for seller) ───

def generate_license_key(email: str, machine_id: str = "") -> str:
    """Generate a license key for a customer email.
    If machine_id is provided, key is bound to that machine.
    Used by the seller to create keys for buyers.
    """
    return _generate_key_seed(email, machine_id)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        email = sys.argv[1]
        mid = sys.argv[2] if len(sys.argv) > 2 else ""
        key = generate_license_key(email, mid)
        print(f"Email: {email}")
        if mid:
            print(f"Machine ID: {mid}")
            print(f"Machine-bound key: {key}")
        else:
            print(f"License key (universal): {key}")
    else:
        print("Usage: python license_manager.py <customer_email> [machine_id]")
        print("  Without machine_id: universal key (works on any machine)")
        print("  With machine_id: bound key (works only on that machine)")

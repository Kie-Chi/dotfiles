"""Secure primitives for the encrypted offline recovery identity."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from envy.keys.storage import current_device_public_key
from envy.secure_io import (
    atomic_write_text,
    ensure_private_directory,
    replace_prepared_file,
    secure_temporary_path,
)
from envy.utils import AGE_KEY_DIR, AGE_KEY_FILE, RECOVERY_KEY_FILE, SECRETS_DIR, run_cmd


def private_key_line(content: str) -> str:
    """Extract one age identity without retaining comments or unrelated text."""
    for line in content.splitlines():
        if line.startswith("AGE-SECRET-KEY"):
            return line
    raise ValueError("age private key content is missing AGE-SECRET-KEY")


def public_key_from_private(private_key: str) -> str:
    """Derive a public recipient without persisting plaintext key material."""
    ensure_private_directory(AGE_KEY_DIR)
    with secure_temporary_path(AGE_KEY_DIR, prefix=".derive-", suffix=".txt") as path:
        atomic_write_text(path, private_key_line(private_key) + "\n", mode=0o600)
        return run_cmd(["age-keygen", "-y", str(path)], capture=True)


def generate_keypair() -> tuple[str, str]:
    """Generate an age identity and return its normalized private/public pair."""
    private_key = private_key_line(run_cmd(["age-keygen"], capture=True))
    return private_key, public_key_from_private(private_key)


def write_encrypted_recovery_key(
    private_key: str,
    recipients: Iterable[str],
) -> None:
    """Encrypt a recovery identity to a prepared file, then atomically replace it."""
    unique_recipients = list(dict.fromkeys(recipient for recipient in recipients if recipient))
    if not unique_recipients:
        raise RuntimeError("no recipients are available for recovery-key.age")
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    with secure_temporary_path(
        SECRETS_DIR, prefix=".recovery-encrypted-", suffix=".age"
    ) as encrypted_path:
        command = ["age", "--encrypt"]
        for recipient in unique_recipients:
            command.extend(["-r", recipient])
        command.extend(["-o", str(encrypted_path)])
        run_cmd(command, stdin_data=private_key_line(private_key) + "\n", capture=True)
        if encrypted_path.stat().st_size == 0:
            raise RuntimeError("age produced an empty recovery key document")
        replace_prepared_file(encrypted_path, RECOVERY_KEY_FILE, mode=0o644)


def decrypt_recovery_key() -> str:
    if not current_device_public_key():
        raise RuntimeError("No current device key")
    return run_cmd(
        ["age", "--decrypt", "-i", str(AGE_KEY_FILE), str(RECOVERY_KEY_FILE)],
        capture=True,
    )


def reencrypt_recovery_key_with(keys: Mapping[str, str]) -> None:
    """Re-encrypt an existing recovery document for the supplied recipient set."""
    if not RECOVERY_KEY_FILE.exists():
        return
    write_encrypted_recovery_key(decrypt_recovery_key(), keys.values())

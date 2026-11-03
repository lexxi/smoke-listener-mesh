#!/usr/bin/env python3
"""Create and verify an ECDSA-P256-signed ESP32-C3 firmware manifest.

This is an OFFLINE release preparation tool. It does not send or flash firmware.
Requires: python -m pip install cryptography
Private keys must never be placed under the repository or transmitted to nodes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

BOARD = "esp32c3"
SCHEMA = "smoke-mesh-ota-v1"
MAX_IMAGE_BYTES = 1310720


def canonical_bytes(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def image_info(path: Path) -> tuple[int, str]:
    sha = hashlib.sha256()
    length = 0
    with path.open("rb") as stream:
        while buf := stream.read(1024 * 1024):
            length += len(buf)
            if length > MAX_IMAGE_BYTES:
                raise ValueError(f"Image exceeds configured 1,310,720 byte OTA slot: {length}")
            sha.update(buf)
    if not length:
        raise ValueError("Image is empty")
    # ESP image header: magic 0xE9, ESP32-C3 chip-id 0x0005 at offset 12.
    with path.open("rb") as stream:
        header = stream.read(24)
    if len(header) < 24 or header[0] != 0xE9:
        raise ValueError("Not an Espressif application image (magic/header mismatch)")
    chip = int.from_bytes(header[12:14], "little")
    if chip != 5:
        raise ValueError(f"Unexpected ESP image chip-id {chip}; expected ESP32-C3 (5)")
    return length, sha.hexdigest()


def make_key(args: argparse.Namespace) -> None:
    target = Path(args.private_key)
    if target.exists():
        raise ValueError("Refusing to overwrite existing private key")
    target.parent.mkdir(parents=True, exist_ok=True)
    secret = ec.generate_private_key(ec.SECP256R1())
    private = secret.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                   serialization.NoEncryption())
    # Exclusively create key file: avoid accidental overwrite, ensure mode 0600 on POSIX.
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(private)
    public = secret.public_key().public_bytes(serialization.Encoding.PEM,
                                                serialization.PublicFormat.SubjectPublicKeyInfo)
    pub_path = Path(args.public_key)
    if pub_path.exists():
        raise ValueError("Public key destination already exists")
    pub_path.write_bytes(public)
    print(f"Private signing key: {target} (DO NOT COMMIT / SHARE)")
    print(f"Public verification key: {pub_path}")


def sign(args: argparse.Namespace) -> None:
    target = args.target.upper()
    if len(target) != 16 or any(c not in "0123456789ABCDEF" for c in target) or target == "0000000000000000":
        raise ValueError("--target requires a nonzero 16-digit hex node ID")
    size, digest = image_info(Path(args.image))
    key = serialization.load_pem_private_key(Path(args.private_key).read_bytes(), password=None)
    if not isinstance(key, ec.EllipticCurvePrivateKey) or not isinstance(key.curve, ec.SECP256R1):
        raise ValueError("Signing key must be ECDSA P-256")
    data = {
        "schema": SCHEMA,
        "board": BOARD,
        "target": target,
        "version": args.version,
        "size": size,
        "sha256": digest,
    }
    signature = key.sign(canonical_bytes(data), ec.ECDSA(hashes.SHA256()))
    manifest = {"signed": data, "signature_der_hex": signature.hex()}
    output = Path(args.out)
    if output.exists() and not args.overwrite:
        raise ValueError("Manifest exists; use --overwrite if intentional")
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Signed {size} bytes sha256={digest}, target={target}, version={args.version}")
    print(f"Manifest: {output}")


def verify(args: argparse.Namespace) -> None:
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    if set(manifest) != {"signed", "signature_der_hex"}:
        raise ValueError("Unexpected manifest envelope")
    signed = manifest["signed"]
    if set(signed) != {"schema", "board", "target", "version", "size", "sha256"}:
        raise ValueError("Unexpected signed fields")
    if signed["schema"] != SCHEMA or signed["board"] != BOARD:
        raise ValueError("Wrong release schema or board")
    size, digest = image_info(Path(args.image))
    if size != signed["size"] or digest != signed["sha256"]:
        raise ValueError("Firmware bytes do not match signed size/hash")
    public = serialization.load_pem_public_key(Path(args.public_key).read_bytes())
    if not isinstance(public, ec.EllipticCurvePublicKey) or not isinstance(public.curve, ec.SECP256R1):
        raise ValueError("Verification key must be ECDSA P-256")
    try:
        public.verify(bytes.fromhex(manifest["signature_der_hex"]),
                      canonical_bytes(signed), ec.ECDSA(hashes.SHA256()))
    except InvalidSignature as exc:
        raise ValueError("Invalid release signature") from exc
    print(f"PASS: signature, board, image size and SHA-256 verified for node {signed['target']}")
    print("NOTE: This verifies an offline manifest; no target firmware installation occurred.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    keygen = sub.add_parser("keygen")
    keygen.add_argument("--private-key", required=True)
    keygen.add_argument("--public-key", required=True)
    keygen.set_defaults(func=make_key)
    signing = sub.add_parser("sign")
    signing.add_argument("--image", required=True)
    signing.add_argument("--private-key", required=True)
    signing.add_argument("--target", required=True)
    signing.add_argument("--version", required=True)
    signing.add_argument("--out", required=True)
    signing.add_argument("--overwrite", action="store_true")
    signing.set_defaults(func=sign)
    checking = sub.add_parser("verify")
    checking.add_argument("--image", required=True)
    checking.add_argument("--manifest", required=True)
    checking.add_argument("--public-key", required=True)
    checking.set_defaults(func=verify)
    args = parser.parse_args()
    try:
        args.func(args)
        return 0
    except (ValueError, OSError, TypeError, KeyError) as exc:
        parser.exit(2, f"ERROR: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())

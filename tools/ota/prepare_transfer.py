#!/usr/bin/env python3
"""Prepare a real ESP32-C3 firmware image for the future ESP-NOW OTA stream.

This tool never opens a serial port and never flashes a device. It verifies an
already signed release against its exact bytes, then outputs fixed-size chunks
and a deterministic transfer plan to support gateway/receiver development.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from sign_release import BOARD, SCHEMA, MAX_IMAGE_BYTES, canonical_bytes, image_info, feature_claim

BLOCK_SIZE = 96


def build_plan(image: Path, manifest: Path, public_key: Path) -> dict:
    # Reuse the existing signing tool's check, not an unsigned SHA from the CLI.
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    envelope = json.loads(manifest.read_text(encoding="utf-8"))
    required_envelope = {"signed", "signature_der_hex"}
    if "feature_claim" in envelope or "feature_signature_der_hex" in envelope:
        required_envelope |= {"feature_claim", "feature_signature_der_hex"}
    if set(envelope) != required_envelope:
        raise ValueError("Unexpected manifest envelope")
    signed = envelope["signed"]
    required = {"schema", "board", "target", "version", "size", "sha256"}
    if not isinstance(signed, dict) or set(signed) != required:
        raise ValueError("Unexpected manifest fields")
    if signed["schema"] != SCHEMA or signed["board"] != BOARD:
        raise ValueError("Unsupported board or manifest schema")
    target = signed["target"]
    if not isinstance(target, str) or len(target) != 16 or any(
        c not in "0123456789ABCDEF" for c in target
    ) or int(target, 16) == 0:
        raise ValueError("Invalid target node ID")
    size, digest = image_info(image)
    if signed["size"] != size or signed["sha256"] != digest:
        raise ValueError("Image size or SHA256 differs from signed manifest")
    if not isinstance(signed["version"], str) or not signed["version"].strip():
        raise ValueError("Invalid version")
    pub = serialization.load_pem_public_key(public_key.read_bytes())
    if not isinstance(pub, ec.EllipticCurvePublicKey) or not isinstance(
        pub.curve, ec.SECP256R1
    ):
        raise ValueError("Expected P-256 verification key")
    try:
        pub.verify(bytes.fromhex(envelope["signature_der_hex"]),
                   canonical_bytes(signed), ec.ECDSA(hashes.SHA256()))
    except InvalidSignature as exc:
        raise ValueError("Invalid firmware publisher signature") from exc
    features = None
    if "feature_claim" in envelope:
        claim = envelope["feature_claim"]
        if not isinstance(claim, dict) or set(claim) != {
            "schema", "firmware_sha256", "target", "version", "features"
        }:
            raise ValueError("Invalid feature claim fields")
        expected_claim = feature_claim(
            claim["features"], digest, target, signed["version"]
        )
        if claim != expected_claim:
            raise ValueError("Feature metadata does not match signed firmware")
        try:
            pub.verify(bytes.fromhex(envelope["feature_signature_der_hex"]),
                       canonical_bytes(claim), ec.ECDSA(hashes.SHA256()))
        except InvalidSignature as exc:
            raise ValueError("Invalid signed feature metadata") from exc
        features = claim["features"]
    count = math.ceil(size / BLOCK_SIZE)
    if size > MAX_IMAGE_BYTES or count > 65535:
        raise ValueError("Image is too large for the planned transport")
    return {
        "schema": "smoke-mesh-transfer-plan-v1",
        "target": target,
        "version": signed["version"],
        "features": features,
        "size": size,
        "sha256": digest,
        "block_size": BLOCK_SIZE,
        "blocks": count,
        "last_block_bytes": size - (count - 1) * BLOCK_SIZE,
        "signed_manifest_sha256": hashlib.sha256(
            canonical_bytes(signed)
        ).hexdigest(),
        "status": "OFFLINE_ONLY_NO_RADIO_NO_FLASH",
    }


def chunks(path: Path):
    with path.open("rb") as fh:
        i = 0
        while block := fh.read(BLOCK_SIZE):
            yield i, block.ljust(BLOCK_SIZE, b"\0")
            i += 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--public-key", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="Plan JSON")
    parser.add_argument("--chunks-out", type=Path, help="Optional line-by-line hex blocks")
    args = parser.parse_args()
    try:
        plan = build_plan(args.image, args.manifest, args.public_key)
        if args.out.exists() or (args.chunks_out and args.chunks_out.exists()):
            raise ValueError("Refusing to overwrite existing output file")
        # Build chunk file only after full verification.
        if args.chunks_out:
            with args.chunks_out.open("x", encoding="ascii", newline="\n") as fd:
                for idx, chunk in chunks(args.image):
                    fd.write(f"{idx:05d} {chunk.hex()}\n")
        args.out.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        print(f"PASS: publisher signature verified; {plan['blocks']} blocks, "
              f"{plan['size']} bytes; target={plan['target']}")
        print("OFFLINE ONLY: no ESP-NOW transmission, no flash writes")
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, f"ERROR: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())

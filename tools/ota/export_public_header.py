#!/usr/bin/env python3
"""Export the public P-256 release key for the ESP32-C3 v0.6.0 verifier.

Never accepts/exports private signing keys.
"""
import argparse
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--public-key",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    key=serialization.load_pem_public_key(a.public_key.read_bytes())
    if not isinstance(key,ec.EllipticCurvePublicKey) or not isinstance(key.curve,ec.SECP256R1):
        p.error("Expected ECDSA P-256 public key, not a private key")
    pem=key.public_bytes(serialization.Encoding.PEM,
                         serialization.PublicFormat.SubjectPublicKeyInfo).decode("ascii")
    if a.out.exists():
        p.error("Refusing to overwrite existing key header")
    a.out.write_text(
        '#pragma once\n'
        '// PUBLIC KEY ONLY; generated from signing-public.pem. Never embed the private key.\n'
        'static const char OTA_PUBLISHER_PUBLIC_KEY_PEM[] = R"PUBKEY(\n'
        + pem.rstrip("\n") + '\n)PUBKEY";\n',encoding="utf-8")
    print(f"Public verifier key exported to {a.out}")


if __name__=="__main__":
    main()

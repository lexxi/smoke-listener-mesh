#!/usr/bin/env python3
"""Send signed release metadata to ESP-NOW target for *device-side* verification.

Requires v0.6.0 gateway and target. No OTA flash writing.
After PASS, invoke send_image.py with same manifest/image and same gateway.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

import serial
from prepare_transfer import build_plan
from sign_release import canonical_bytes

BLOCK=96


def corrupt_signature_for_negative_test(payload: bytes) -> bytes:
    """Corrupt ONLY a DER signature byte, never the on-disk manifest.

    Flip a bit in the last signature byte, retaining all wire lengths and
    the DER envelope so the device reaches cryptographic verification.
    """
    data=bytearray(payload)
    if len(data)<8 or int.from_bytes(data[:2],"little")!=len(data):
        raise ValueError("Invalid manifest wire envelope")
    siglen=data[4+int.from_bytes(data[2:4],"little")]
    if siglen<68 or siglen>80 or 5+int.from_bytes(data[2:4],"little")+siglen!=len(data):
        raise ValueError("Invalid DER signature boundary")
    data[-1]^=1
    return bytes(data)


def encode_manifest(path: Path) -> bytes:
    envelope=json.loads(path.read_text(encoding="utf-8"))
    canonical=canonical_bytes(envelope["signed"])
    sig=bytes.fromhex(envelope["signature_der_hex"])
    if not 68<=len(sig)<=80 or len(canonical)>420:
        raise ValueError("Unexpected signature length or canonical JSON size")
    inner=len(canonical).to_bytes(2,"little")+canonical+bytes([len(sig)])+sig
    payload=len(inner+bytes(2)).to_bytes(2,"little")+inner
    if len(payload)>576:
        raise ValueError("Manifest exceeds target buffer")
    return payload


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port",required=True)
    p.add_argument("--image",type=Path,required=True)
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--public-key",type=Path,required=True)
    p.add_argument("--timeout",type=float,default=120)
    p.add_argument("--test-invalid-signature",action="store_true",
                   help="Corrupt signature IN MEMORY after local verification; PASS only if target rejects it")
    p.add_argument("--baud",type=int,default=115200)
    args=p.parse_args()
    try:
        plan=build_plan(args.image,args.manifest,args.public_key)
        payload=encode_manifest(args.manifest)
        if args.test_invalid_signature:
            payload=corrupt_signature_for_negative_test(payload)
    except (ValueError,KeyError,TypeError,OSError) as e:
        p.exit(2,f"ERROR: signed manifest validation: {e}\n")
    count=(len(payload)+BLOCK-1)//BLOCK
    if args.test_invalid_signature:
        print("NEGATIVE TEST: modified signature bytes in RAM; expecting target rejection")
    print(f"Verified release {plan['version']}, target {plan['target']}, "
          f"manifest {len(payload)} bytes/{count} packets; NO_FLASH")
    try:
        with serial.Serial(args.port,args.baud,timeout=1,write_timeout=5) as port:
            time.sleep(3)
            port.reset_input_buffer()
            port.write(f"AUTH BEGIN {plan['target']} {len(payload)}\n".encode("ascii"))
            port.flush()
            deadline=time.monotonic()+args.timeout
            expected=0
            while time.monotonic()<deadline:
                line=port.readline().decode("utf-8","replace").strip()
                if not line:
                    continue
                if "[AUTH]" in line:print(line,flush=True)
                m=re.search(r"\[AUTH\] NEXT index=(\d+)/(\d+)\b",line)
                if m:
                    index,total=map(int,m.groups())
                    if total!=count or index!=expected or index>=count:
                        port.write(b"AUTH STOP\n")
                        print("FAIL: unexpected chunk index",file=sys.stderr)
                        return 1
                    part=payload[index*BLOCK:(index+1)*BLOCK].ljust(BLOCK,b"\x00")
                    port.write(b"AUTH DATA "+part.hex().encode("ascii")+b"\n")
                    port.flush()
                    expected+=1
                if "[AUTH] PASS" in line and "VERIFIED_ON_DEVICE" in line:
                    if args.test_invalid_signature:
                        print("FAIL: target accepted deliberately corrupted signature!",file=sys.stderr)
                        return 1
                    print("PASS: ECDSA P-256 signature verified by target (no flash).")
                    return 0
                if "[AUTH] FAIL signature_rejected" in line:
                    if args.test_invalid_signature:
                        print("PASS: target REJECTED corrupted signature; no flash.")
                        return 0
                    return 1
                if "[AUTH] FAIL" in line or "[AUTH] ERROR" in line:
                    return 1
            port.write(b"AUTH STOP\n")
            print("FAIL: timeout awaiting target verification",file=sys.stderr)
            return 1
    except (serial.SerialException,OSError) as e:
        print(f"ERROR: serial port: {e}",file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())

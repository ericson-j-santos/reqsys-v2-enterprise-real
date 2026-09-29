from __future__ import annotations

import argparse
import hashlib
import json
import os
import wave
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_evidence(
    evidence_path: Path,
    output_root: Path,
    expected_sha: str,
    expected_host: str = "NOTERI",
) -> list[str]:
    errors: list[str] = []
    if not evidence_path.exists():
        return ["evidence_missing"]

    data = json.loads(evidence_path.read_text(encoding="utf-8"))
    if data.get("ok") is not True:
        errors.append("evidence_not_ok")
    if str(data.get("host", "")).upper() != expected_host.upper():
        errors.append("host_mismatch")
    if str(data.get("expected_sha", "")).lower() != expected_sha.lower():
        errors.append("expected_sha_mismatch")
    if str(data.get("observed_sha", "")).lower() != expected_sha.lower():
        errors.append("observed_sha_mismatch")
    if data.get("paid_service") is not False:
        errors.append("paid_service_detected")
    if data.get("production_touched") is not False:
        errors.append("production_touched")
    if data.get("secrets_read") is not False:
        errors.append("secrets_read")
    if data.get("segments_expected") != 10:
        errors.append("segment_contract_mismatch")

    files = data.get("files") or []
    if len(files) != 20:
        errors.append(f"file_count_mismatch:{len(files)}")

    voices = data.get("voices") or []
    expected_pairs = {(str(voice), segment) for voice in voices for segment in range(1, 11)}
    observed_pairs: set[tuple[str, int]] = set()
    hashes: set[str] = set()

    for item in files:
        voice = str(item.get("voice", ""))
        segment_id = int(item.get("segment_id", 0) or 0)
        observed_pairs.add((voice, segment_id))
        rel = str(item.get("relative_path", ""))
        wav = (output_root / rel).resolve()
        try:
            wav.relative_to(output_root.resolve())
        except ValueError:
            errors.append(f"path_escape:{rel}")
            continue
        if not wav.exists():
            errors.append(f"file_missing:{rel}")
            continue
        if wav.stat().st_size < 1000:
            errors.append(f"file_too_small:{rel}")
            continue
        actual_hash = sha256(wav)
        if actual_hash != item.get("sha256"):
            errors.append(f"sha_mismatch:{rel}")
        hashes.add(actual_hash)
        try:
            with wave.open(str(wav), "rb") as handle:
                frames = handle.getnframes()
                rate = handle.getframerate()
                channels = handle.getnchannels()
                payload = handle.readframes(frames)
            if rate < 16000:
                errors.append(f"sample_rate_too_low:{rel}")
            if channels not in (1, 2):
                errors.append(f"invalid_channels:{rel}")
            if frames <= int(rate * 0.2):
                errors.append(f"duration_too_short:{rel}")
            if not any(payload):
                errors.append(f"silence_detected:{rel}")
        except wave.Error:
            errors.append(f"wave_read_failed:{rel}")

    if observed_pairs != expected_pairs:
        errors.append("voice_segment_matrix_incomplete")
    if len(hashes) != len(files):
        errors.append("duplicate_or_missing_hashes")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--expected-sha", required=True)
    args = parser.parse_args()

    errors = validate_evidence(
        Path(args.evidence).resolve(),
        Path(args.output_root).resolve(),
        args.expected_sha,
    )
    result = {
        "ok": not errors,
        "host": os.environ.get("COMPUTERNAME", ""),
        "expected_sha": args.expected_sha,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())

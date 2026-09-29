from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import venv
from pathlib import Path
from typing import Any

CONFIRM = "GENERATE-IA-QUE-TRABALHA-NEURAL-TTS"

SEGMENTS = [
    {"id": 1, "start_s": 0.000000, "end_s": 1.931202, "text": "Essa planilha tem três erros. Você consegue achar em dez segundos?"},
    {"id": 2, "start_s": 2.323039, "end_s": 5.046440, "text": "Pare de revisar linha por linha. Use a IA para reduzir o espaço de busca."},
    {"id": 3, "start_s": 5.411519, "end_s": 7.706576, "text": "Selecione os dados e aplique o prompt."},
    {"id": 4, "start_s": 7.909660, "end_s": 11.988753, "text": "Encontre duplicados, datas inválidas e valores muito fora do padrão."},
    {"id": 5, "start_s": 12.184308, "end_s": 15.016735, "text": "Retorne a linha, o problema e o motivo."},
    {"id": 6, "start_s": 15.438458, "end_s": 18.934422, "text": "A análise encontrou três suspeitas. Você continua decidindo."},
    {"id": 7, "start_s": 19.209070, "end_s": 20.349524, "text": "A IA não corrigiu nada."},
    {"id": 8, "start_s": 20.524671, "end_s": 24.102902, "text": "Ela mostrou onde olhar primeiro: duplicidade, data inválida e valor fora do padrão."},
    {"id": 9, "start_s": 24.512562, "end_s": 25.439909, "text": "A IA filtra. Você valida."},
    {"id": 10, "start_s": 25.868073, "end_s": 28.290567, "text": "Confira sempre no arquivo original."},
]

KOKORO_VOICES = ("pf_dora", "pm_alex")
PIPER_VOICES = ("pt_BR-cadu-medium", "pt_BR-faber-medium")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(args: list[str], *, timeout: int, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, input=input_text, text=True, capture_output=True, timeout=timeout, check=False)


def _python_in_venv(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _install(python: Path, packages: list[str], *, timeout: int = 420) -> None:
    result = _run(
        [str(python), "-m", "pip", "install", "--disable-pip-version-check", "--no-input", *packages],
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError("pip_install_failed:" + " ".join(packages) + ":" + (result.stderr[-2000:] or result.stdout[-2000:]))


def _wav_meta(path: Path) -> dict[str, Any]:
    import numpy as np
    import soundfile as sf

    info = sf.info(str(path))
    data, _ = sf.read(str(path), dtype="float32", always_2d=False)
    rms = float(np.sqrt(np.mean(np.square(data)))) if len(data) else 0.0
    return {
        "samplerate": int(info.samplerate),
        "frames": int(info.frames),
        "duration_s": round(float(info.duration), 6),
        "channels": int(info.channels),
        "rms": round(rms, 8),
        "sha256": _sha256(path),
        "size_bytes": path.stat().st_size,
    }


def _generate_kokoro(output_root: Path) -> list[dict[str, Any]]:
    import numpy as np
    import soundfile as sf

    try:
        import espeakng_loader

        espeakng_loader.make_library_available()
        if hasattr(espeakng_loader, "get_library_path"):
            os.environ["PHONEMIZER_ESPEAK_LIBRARY"] = str(espeakng_loader.get_library_path())
        if hasattr(espeakng_loader, "get_data_path"):
            os.environ["PHONEMIZER_ESPEAK_PATH"] = str(espeakng_loader.get_data_path())
    except Exception:
        pass

    from kokoro import KPipeline

    pipeline = KPipeline(lang_code="p")
    files: list[dict[str, Any]] = []
    for voice in KOKORO_VOICES:
        voice_dir = output_root / "kokoro" / voice
        voice_dir.mkdir(parents=True, exist_ok=True)
        for segment in SEGMENTS:
            pieces: list[Any] = []
            for _, _, audio in pipeline(segment["text"], voice=voice, speed=1.0):
                pieces.append(np.asarray(audio, dtype=np.float32))
            if not pieces:
                raise RuntimeError(f"kokoro_empty_audio:{voice}:{segment['id']}")
            wav = voice_dir / f"segment_{segment['id']:02d}.wav"
            sf.write(str(wav), np.concatenate(pieces), 24000)
            meta = _wav_meta(wav)
            if meta["duration_s"] <= 0.2 or meta["rms"] <= 0.001:
                raise RuntimeError(f"kokoro_invalid_audio:{voice}:{segment['id']}")
            files.append({
                "engine": "kokoro",
                "voice": voice,
                "segment_id": segment["id"],
                "start_s": segment["start_s"],
                "end_s": segment["end_s"],
                "target_duration_s": round(segment["end_s"] - segment["start_s"], 6),
                "text": segment["text"],
                "relative_path": str(wav.relative_to(output_root)).replace("\\", "/"),
                **meta,
            })
    return files


def _download_piper_voice(python: Path, model_dir: Path, voice: str) -> Path:
    model_dir.mkdir(parents=True, exist_ok=True)
    result = _run(
        [str(python), "-m", "piper.download_voices", "--download-dir", str(model_dir), voice],
        timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(f"piper_voice_download_failed:{voice}:{result.stderr[-1600:]}")
    model = model_dir / f"{voice}.onnx"
    if not model.exists():
        raise RuntimeError(f"piper_model_missing:{voice}")
    return model


def _generate_piper(output_root: Path, python: Path) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    model_dir = output_root / "piper" / "models"
    for voice in PIPER_VOICES:
        model = _download_piper_voice(python, model_dir, voice)
        voice_dir = output_root / "piper" / voice
        voice_dir.mkdir(parents=True, exist_ok=True)
        for segment in SEGMENTS:
            wav = voice_dir / f"segment_{segment['id']:02d}.wav"
            result = _run(
                [str(python), "-m", "piper", "--model", str(model), "--output_file", str(wav)],
                input_text=segment["text"],
                timeout=120,
            )
            if result.returncode != 0:
                raise RuntimeError(f"piper_generation_failed:{voice}:{segment['id']}:{result.stderr[-1600:]}")
            if not wav.exists():
                raise RuntimeError(f"piper_audio_missing:{voice}:{segment['id']}")
            meta = _wav_meta(wav)
            if meta["duration_s"] <= 0.2 or meta["rms"] <= 0.001:
                raise RuntimeError(f"piper_invalid_audio:{voice}:{segment['id']}")
            files.append({
                "engine": "piper",
                "voice": voice,
                "segment_id": segment["id"],
                "start_s": segment["start_s"],
                "end_s": segment["end_s"],
                "target_duration_s": round(segment["end_s"] - segment["start_s"], 6),
                "text": segment["text"],
                "relative_path": str(wav.relative_to(output_root)).replace("\\", "/"),
                **meta,
            })
    return files


def _worker(engine: str, output_root: Path) -> int:
    files = _generate_kokoro(output_root) if engine == "kokoro" else _generate_piper(output_root, Path(sys.executable))
    result = {"ok": True, "engine": engine, "voices": sorted({item["voice"] for item in files}), "files": files}
    result_path = output_root / f"{engine}-worker-result.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(result_path)
    return 0


def _invoke_worker(python: Path, engine: str, output_root: Path) -> dict[str, Any]:
    result = _run(
        [str(python), str(Path(__file__).resolve()), "--worker-engine", engine, "--output-root", str(output_root)],
        timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(f"{engine}_worker_failed:rc={result.returncode}:" + (result.stderr[-2400:] or result.stdout[-2400:]))
    result_path = output_root / f"{engine}-worker-result.json"
    if not result_path.exists():
        raise RuntimeError(f"{engine}_worker_result_missing")
    data = json.loads(result_path.read_text(encoding="utf-8"))
    if not data.get("ok"):
        raise RuntimeError(f"{engine}_worker_not_ok")
    return data


def generate(*, expected_sha: str, output_root: Path, evidence_path: Path) -> int:
    output_root.mkdir(parents=True, exist_ok=True)
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    host = os.environ.get("COMPUTERNAME", "")
    observed_sha = os.environ.get("GITHUB_SHA", "")
    evidence: dict[str, Any] = {
        "ok": False,
        "host": host,
        "expected_sha": expected_sha,
        "observed_sha": observed_sha,
        "paid_service": False,
        "production_touched": False,
        "secrets_read": False,
        "segments_expected": len(SEGMENTS),
        "attempts": [],
    }

    if host.upper() != "NOTERI":
        evidence["error"] = f"host_mismatch:{host}"
        evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 2
    if observed_sha.lower() != expected_sha.lower():
        evidence["error"] = f"sha_mismatch:{observed_sha}"
        evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 2

    venv_dir = output_root / "venv"
    try:
        if not _python_in_venv(venv_dir).exists():
            venv.EnvBuilder(with_pip=True, system_site_packages=True).create(venv_dir)
        python = _python_in_venv(venv_dir)
        if not python.exists():
            raise RuntimeError("venv_python_missing")

        try:
            _install(python, ["kokoro>=0.9.4,<1.0", "soundfile>=0.12,<1.0", "espeakng-loader==0.2.4"])
            result = _invoke_worker(python, "kokoro", output_root)
            evidence["attempts"].append({"engine": "kokoro", "ok": True})
        except Exception as kokoro_exc:
            evidence["attempts"].append({
                "engine": "kokoro",
                "ok": False,
                "error_type": type(kokoro_exc).__name__,
                "error": str(kokoro_exc)[:2400],
            })
            _install(python, ["piper-tts>=1.2,<2.0", "soundfile>=0.12,<1.0"])
            result = _invoke_worker(python, "piper", output_root)
            evidence["attempts"].append({"engine": "piper", "ok": True})

        evidence["engine"] = result["engine"]
        evidence["voices"] = result["voices"]
        evidence["files"] = result["files"]
        files = evidence["files"]
        if len(files) != len(SEGMENTS) * 2:
            raise RuntimeError(f"file_count_mismatch:{len(files)}:{len(SEGMENTS) * 2}")
        if len(set(item["sha256"] for item in files)) != len(files):
            raise RuntimeError("duplicate_audio_hash_detected")
        evidence["files_generated"] = len(files)
        evidence["ok"] = True
    except Exception as exc:
        evidence["error_type"] = type(exc).__name__
        evidence["error"] = str(exc)[:3000]

    evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "ok": evidence["ok"],
        "engine": evidence.get("engine"),
        "voices": evidence.get("voices"),
        "files_generated": evidence.get("files_generated", 0),
        "attempts": evidence["attempts"],
    }, ensure_ascii=False))
    return 0 if evidence["ok"] else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm")
    parser.add_argument("--expected-sha")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--evidence")
    parser.add_argument("--worker-engine", choices=("kokoro", "piper"))
    args = parser.parse_args()
    output_root = Path(args.output_root).resolve()

    if args.worker_engine:
        return _worker(args.worker_engine, output_root)
    if args.confirm != CONFIRM:
        print("confirmation_missing", file=sys.stderr)
        return 2
    if not args.expected_sha or not args.evidence:
        print("expected_sha_and_evidence_required", file=sys.stderr)
        return 2
    return generate(
        expected_sha=args.expected_sha,
        output_root=output_root,
        evidence_path=Path(args.evidence).resolve(),
    )


if __name__ == "__main__":
    raise SystemExit(main())

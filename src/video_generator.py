"""Veo 3.1 ile video üretici — google-genai SDK, GEMINI_API_KEY ile çalışır."""

import os
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

OUTPUT_DIR = Path(__file__).parent.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

VEO_MODEL = "veo-3.1-generate-preview"
POLL_INTERVAL = 10   # saniye — operation tamamlanana kadar ne sıklıkla sorulsun
POLL_TIMEOUT = 600   # saniye — maksimum bekleme süresi


def _client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY ortam değişkeni ayarlanmamış.")
    return genai.Client(api_key=api_key)


def _poll_operation(client: genai.Client, operation: types.GenerateVideosOperation) -> types.GenerateVideosOperation:
    """Operation tamamlanana kadar polling yapar."""
    elapsed = 0
    while not operation.done:
        if elapsed >= POLL_TIMEOUT:
            raise TimeoutError(f"Veo operasyonu {POLL_TIMEOUT}s içinde tamamlanamadı.")
        logger.info(f"  Veo üretiyor... ({elapsed}s geçti, her {POLL_INTERVAL}s'de kontrol)")
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
        operation = client.operations.get(operation)
    return operation


@retry(
    stop=stop_after_attempt(int(os.getenv("RETRY_ATTEMPTS", 3))),
    wait=wait_exponential(multiplier=1, min=15, max=60),
    reraise=True,
)
def generate_scene_video(
    prompt: str,
    duration_seconds: int,
    output_filename: str,
    aspect_ratio: str = "9:16",
    resolution: str = "1080p",
    model_name: Optional[str] = None,
) -> Path:
    """
    Tek bir sahne için Veo 3.1 ile video üretir.

    Döndürür: kaydedilen video dosyasının Path'i
    """
    model_id = model_name or os.getenv("VEO_MODEL", VEO_MODEL)
    client = _client()
    output_path = OUTPUT_DIR / output_filename

    logger.info(f"Video üretimi başlatılıyor: {output_filename}")
    logger.debug(f"Model: {model_id} | Süre: {duration_seconds}s | Çözünürlük: {resolution} | Oran: {aspect_ratio}")
    logger.debug(f"Prompt: {prompt[:120]}...")

    operation = client.models.generate_videos(
        model=model_id,
        prompt=prompt,
        config=types.GenerateVideosConfig(
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            duration_seconds=duration_seconds,
            number_of_videos=1,
            fps=int(os.getenv("VIDEO_FPS", 24)),
            enhance_prompt=True,
            person_generation="allow_adult",
        ),
    )

    operation = _poll_operation(client, operation)

    if operation.error:
        raise RuntimeError(f"Veo API hatası: {operation.error}")

    response: types.GenerateVideosResponse = operation.response
    if not response or not response.generated_videos:
        raise RuntimeError("Veo API boş yanıt döndürdü.")

    video: types.Video = response.generated_videos[0].video

    if video.video_bytes:
        output_path.write_bytes(video.video_bytes)
    elif video.uri:
        _download_from_uri(video.uri, output_path)
    else:
        raise RuntimeError("Video verisi alınamadı (ne bytes ne uri).")

    logger.success(f"Video kaydedildi: {output_path} ({output_path.stat().st_size // 1024} KB)")
    return output_path


def generate_full_video(script: dict) -> Path:
    """
    Bir senaryo için tüm sahneleri üretip birleştirir.

    Döndürür: birleşik final video dosyasının Path'i
    """
    question_id = script["metadata"]["question_id"]
    scene_paths = []

    for veo_prompt_entry in script["veo_prompts"]:
        scene_id = veo_prompt_entry["scene_id"]
        prompt = veo_prompt_entry["prompt"]
        scene = next(s for s in script["scenes"] if s["id"] == scene_id)
        duration = scene["duration_seconds"]

        filename = f"q{question_id:02d}_{scene_id}.mp4"
        scene_path = generate_scene_video(
            prompt=prompt,
            duration_seconds=duration,
            output_filename=filename,
        )
        scene_paths.append(scene_path)

    final_path = _concatenate_scenes(scene_paths, question_id)
    return final_path


def _download_from_uri(uri: str, local_path: Path) -> None:
    """GCS veya HTTPS URI'den dosya indirir."""
    if uri.startswith("gs://"):
        from google.cloud import storage
        bucket_name, blob_name = uri[5:].split("/", 1)
        storage.Client().bucket(bucket_name).blob(blob_name).download_to_filename(str(local_path))
    else:
        import urllib.request
        urllib.request.urlretrieve(uri, str(local_path))


def _concatenate_scenes(scene_paths: list[Path], question_id: int) -> Path:
    """moviepy ile sahne videolarını sırayla birleştirir."""
    from moviepy.editor import VideoFileClip, concatenate_videoclips

    clips = [VideoFileClip(str(p)) for p in scene_paths]
    final = concatenate_videoclips(clips, method="compose")
    output_path = OUTPUT_DIR / f"q{question_id:02d}_final.mp4"

    final.write_videofile(
        str(output_path),
        fps=int(os.getenv("VIDEO_FPS", 24)),
        codec="libx264",
        audio_codec="aac",
    )

    for clip in clips:
        clip.close()
    final.close()

    logger.success(f"Final video birleştirildi: {output_path}")
    return output_path

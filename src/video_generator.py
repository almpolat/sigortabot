"""Veo 3.1 ile video üretici — Google Vertex AI üzerinden çalışır."""

import os
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

OUTPUT_DIR = Path(__file__).parent.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

VIDEO_WIDTH = int(os.getenv("VIDEO_WIDTH", 1080))
VIDEO_HEIGHT = int(os.getenv("VIDEO_HEIGHT", 1920))

# Veo 3.1 desteklenen süreler (saniye)
VEO_SUPPORTED_DURATIONS = {2, 4, 6, 8}


def init_vertex():
    import vertexai  # lazy import — sadece gerçek video üretiminde gerekli
    project_id = os.getenv("GOOGLE_PROJECT_ID")
    location = os.getenv("GOOGLE_LOCATION", "us-central1")
    if not project_id:
        raise EnvironmentError("GOOGLE_PROJECT_ID ortam değişkeni ayarlanmamış.")
    vertexai.init(project=project_id, location=location)


@retry(
    stop=stop_after_attempt(int(os.getenv("RETRY_ATTEMPTS", 3))),
    wait=wait_exponential(
        multiplier=1,
        min=int(os.getenv("RETRY_DELAY_SECONDS", 30)),
        max=120,
    ),
)
def generate_scene_video(
    prompt: str,
    duration_seconds: int,
    output_filename: str,
    aspect_ratio: str = "9:16",
    model_name: Optional[str] = None,
) -> Path:
    """
    Tek bir sahne için Veo 3.1 ile video üretir.
    Döndürür: üretilen video dosyasının Path'i
    """
    if duration_seconds not in VEO_SUPPORTED_DURATIONS:
        duration_seconds = min(
            VEO_SUPPORTED_DURATIONS, key=lambda x: abs(x - duration_seconds)
        )
        logger.warning(f"Süre desteklenmiyor, en yakına yuvarlandı: {duration_seconds}s")

    init_vertex()
    from vertexai.preview.vision_models import VideoGenerationModel  # lazy import
    model_id = model_name or os.getenv("VEO_MODEL", "veo-3.1-generate-preview")
    model = VideoGenerationModel.from_pretrained(model_id)

    logger.info(f"Video üretiliyor: {output_filename} ({duration_seconds}s)")
    logger.debug(f"Prompt: {prompt[:100]}...")

    output_path = OUTPUT_DIR / output_filename

    operation = model.generate_video(
        prompt=prompt,
        target_video_duration_seconds=duration_seconds,
        aspect_ratio=aspect_ratio,
        output_gcs_uri=f"gs://{os.getenv('GOOGLE_PROJECT_ID')}-sigortabot/{output_filename}",
    )

    # Asenkron işlemi bekle (Veo üretimi uzun sürebilir)
    logger.info("Veo üretimi bekleniyor...")
    result = operation.result(timeout=600)

    # GCS'den yerel dizine indir
    _download_from_gcs(result.videos[0].uri, output_path)

    logger.success(f"Video indirildi: {output_path}")
    return output_path


def generate_full_video(script: dict) -> Path:
    """
    Bir senaryo için tüm sahneleri üretip birleştirir.
    Döndürür: birleşik video dosyasının Path'i
    """
    question_id = script["metadata"]["question_id"]
    scene_paths = []

    for veo_prompt in script["veo_prompts"]:
        scene_id = veo_prompt["scene_id"]
        prompt = veo_prompt["prompt"]

        # Sahne süresini scenes listesinden bul
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


def _download_from_gcs(gcs_uri: str, local_path: Path) -> None:
    """GCS URI'den yerel dosyaya indirir."""
    from google.cloud import storage

    bucket_name, blob_name = gcs_uri.replace("gs://", "").split("/", 1)
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.download_to_filename(str(local_path))


def _concatenate_scenes(scene_paths: list[Path], question_id: int) -> Path:
    """moviepy ile sahne videolarını birleştirir."""
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

    logger.success(f"Final video: {output_path}")
    return output_path

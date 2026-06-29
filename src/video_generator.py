"""Kling v2.1 ile video üretici — fal-ai client, FAL_KEY ile çalışır."""

import os
from pathlib import Path
from typing import Optional

import fal_client
from dotenv import load_dotenv
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

OUTPUT_DIR = Path(__file__).parent.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

FAL_MODEL = "fal-ai/kling-video"


def _set_fal_key() -> None:
    key = os.getenv("FAL_KEY")
    if not key:
        raise EnvironmentError("FAL_KEY ortam değişkeni ayarlanmamış.")
    os.environ["FAL_KEY"] = key


@retry(
    stop=stop_after_attempt(int(os.getenv("RETRY_ATTEMPTS", 3))),
    wait=wait_exponential(multiplier=1, min=10, max=60),
    reraise=True,
)
def generate_scene_video(
    prompt: str,
    output_filename: str,
    aspect_ratio: str = "9:16",
    duration: str = "5",
    model: Optional[str] = None,
) -> Path:
    """
    Kling v2.1 ile video üretir ve output/ altına MP4 olarak kaydeder.
    Döndürür: kaydedilen dosyanın Path'i
    """
    _set_fal_key()
    model_id = model or os.getenv("FAL_MODEL", FAL_MODEL)
    output_path = OUTPUT_DIR / output_filename

    logger.info(f"Video üretimi başlatılıyor: {output_filename}")
    logger.debug(f"Model: {model_id} | Süre: {duration}s | Oran: {aspect_ratio}")
    logger.debug(f"Prompt: {prompt[:120]}...")

    result = fal_client.run(
        model_id,
        arguments={
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "duration": duration,
        },
    )

    video_url = result["video"]["url"]
    logger.info(f"Video URL alındı, indiriliyor: {video_url[:60]}...")

    import urllib.request
    urllib.request.urlretrieve(video_url, str(output_path))

    size_kb = output_path.stat().st_size // 1024
    logger.success(f"Video kaydedildi: {output_path} ({size_kb} KB)")
    return output_path


def generate_full_video(script: dict) -> Path:
    """
    Senaryodaki 3 sahneyi tek bir Kling promptuna birleştirip üretir.
    Döndürür: kaydedilen video dosyasının Path'i
    """
    question_id = script["metadata"]["question_id"]

    prompts_by_scene = {e["scene_id"]: e["prompt"] for e in script["veo_prompts"]}
    hook_prompt  = prompts_by_scene.get("hook", "")
    main_prompt  = prompts_by_scene.get("main", "")
    punch_prompt = prompts_by_scene.get("punchline", "")

    combined_prompt = (
        f"A 5-second vertical (9:16) cartoon animation in three acts. "
        f"FIRST act — Hook: {hook_prompt} "
        f"SECOND act — Main scene: {main_prompt} "
        f"THIRD act — Punchline: {punch_prompt}"
    )

    filename = f"q{question_id:02d}_final.mp4"
    return generate_scene_video(
        prompt=combined_prompt,
        output_filename=filename,
    )

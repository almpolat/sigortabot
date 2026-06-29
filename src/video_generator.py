"""fal-ai/veo3 ile video üretici — FAL_KEY ile çalışır."""

import os
import urllib.request
from pathlib import Path
from typing import Optional

import fal_client
from dotenv import load_dotenv
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

OUTPUT_DIR = Path(__file__).parent.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

FAL_MODEL = "fal-ai/veo3"

CHARACTER_MAP = {
    "cockroach": "adorable anthropomorphic cockroach",
    "fox":       "clever anthropomorphic fox in suit",
    "chicken":   "nervous anthropomorphic chicken",
    "bear":      "big emotional anthropomorphic bear",
    "cat":       "dramatic anthropomorphic cat",
    "pigeon":    "wise tired anthropomorphic pigeon",
    "mouse":     "tiny brave anthropomorphic mouse",
}


def _set_fal_key() -> None:
    key = os.getenv("FAL_KEY")
    if not key:
        raise EnvironmentError("FAL_KEY ortam değişkeni ayarlanmamış.")
    os.environ["FAL_KEY"] = key


def build_prompt(script: dict) -> str:
    """Script JSON'dan sade bir veo3 sahnesi promptu üretir."""
    meta = script["metadata"]
    character_key = meta.get("karakter", "cockroach")
    character_desc = CHARACTER_MAP.get(character_key, f"anthropomorphic {character_key}")

    scenes_by_id = {s["id"]: s for s in script["scenes"]}
    punchline = scenes_by_id.get("punchline", {}).get("on_screen_text", "")

    return (
        f"{character_desc} sitting in a cozy Turkish living room, "
        f"watching TV and reacting with shock to insurance news. "
        f"The character looks at camera with surprised expression and says '{punchline}'. "
        f"Photorealistic animation, 9:16 vertical, 4K, cinematic lighting, 8 seconds."
    )


@retry(
    stop=stop_after_attempt(int(os.getenv("RETRY_ATTEMPTS", 3))),
    wait=wait_exponential(multiplier=1, min=10, max=60),
    reraise=True,
)
def generate_scene_video(
    prompt: str,
    output_filename: str,
    aspect_ratio: str = "9:16",
    duration: str = "8s",
    model: Optional[str] = None,
) -> Path:
    """Promptu veo3'e gönderir, video üretilince output/ altına MP4 kaydeder."""
    _set_fal_key()
    model_id = model or os.getenv("FAL_MODEL", FAL_MODEL)
    output_path = OUTPUT_DIR / output_filename

    logger.info(f"Video üretimi başlatılıyor: {output_filename}")
    logger.debug(f"Model: {model_id} | Süre: {duration}s | Oran: {aspect_ratio}")
    logger.debug(f"Prompt: {prompt[:120]}...")

    def on_queue_update(update):
        if hasattr(update, "logs") and update.logs:
            for log in update.logs:
                logger.debug(f"[fal] {log.get('message', '')}")

    result = fal_client.subscribe(
        model_id,
        arguments={
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "duration": duration,
        },
        with_logs=True,
        on_queue_update=on_queue_update,
    )

    video_url = result["video"]["url"]
    logger.info(f"Video URL alındı, indiriliyor: {video_url[:60]}...")

    urllib.request.urlretrieve(video_url, str(output_path))

    size_kb = output_path.stat().st_size // 1024
    logger.success(f"Video kaydedildi: {output_path} ({size_kb} KB)")
    return output_path


def generate_full_video(script: dict) -> Path:
    """Script JSON'dan prompt üretip videoyu kaydeder, Path döndürür."""
    question_id = script["metadata"]["question_id"]
    prompt = build_prompt(script)
    filename = f"q{question_id:02d}_final.mp4"
    logger.debug(f"Oluşturulan prompt ({len(prompt)} karakter):\n{prompt}")
    return generate_scene_video(prompt=prompt, output_filename=filename)

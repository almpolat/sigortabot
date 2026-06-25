"""Veo 3.1 için video senaryosu üretici (Gemini ile)."""

import json
import os
from pathlib import Path
from typing import Optional

import google.generativeai as genai
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
SCRIPTS_DIR.mkdir(exist_ok=True)

CHARACTERS_DIR = Path(__file__).parent.parent / "characters"

# Sahne süresi sabitleri (saniye)
SCENE_HOOK_END = 2
SCENE_MAIN_END = 6
SCENE_TOTAL = 8

SYSTEM_PROMPT = """Sen Türkiye'nin en komik sigorta animasyon videolarını yazan bir senaristsin.
Her video tam olarak 8 saniye, 1080x1920 (9:16 dikey) formatında ve 3 sahneden oluşuyor:
- Hook (0-2s): Karakter kameraya bakıyor, şaşkın/meraklı ifade, hook metni ekranda
- Komik Sahne (2-6s): Sigorta sorusunu komik bir şekilde canlandıran durum
- Punch Line (6-8s): Karakter kameraya dönüp kısa ve akılda kalıcı bir şey söylüyor

Karakter kişilikleri:
- cockroach (Hamamböceği): Her şeyden sağ kurtulan, hiçbir şeyden etkilenmeyen
- cat (Kedi): Her şeyi bilen havası taşıyan ama aslında hiçbir şey bilmeyen
- fox (Tilki): Kurnaz, her zaman bir çözüm yolu arayan
- chicken (Tavuk): Aşırı endişeli, her şeyden korkan
- bear (Ayı): Büyük ve sakin ama sıradan şeyler karşısında şaşıran
- pigeon (Güvercin): Şehirli, her yerde gezen, çok şey bilen
- mouse (Fare): Küçük ama akıllı, her deliği biliyor

Veo 3.1 için prompt kuralları:
- Sahne açıklamaları İngilizce olmalı (Veo İngilizce promptla daha iyi çalışır)
- Karakter hareketlerini net tanımla
- Kamera açısını belirt (close-up, medium shot, wide shot)
- Arka plan ve ortamı kısaca tanımla
- Komik abartı önemli: büyük gözler, abartılı tepkiler, karikatür fizik
"""


def load_character_config(character_name: str) -> dict:
    config_path = CHARACTERS_DIR / f"{character_name}.json"
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            return json.load(f)
    return {"name": character_name, "style": "3D cartoon animation"}


def generate_video_script(question: dict, model_name: Optional[str] = None) -> dict:
    """
    Veo 3.1 için 3 sahneli video senaryosu üretir.
    Döndürür: {scenes: [...], veo_prompts: [...], metadata: {...}}
    """
    model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY ortam değişkeni ayarlanmamış.")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name, system_instruction=SYSTEM_PROMPT)

    character = question["en_uygun_karakter"]
    char_config = load_character_config(character)

    user_prompt = f"""
Şu sigorta sorusu için 8 saniyelik komik animasyon videosu senaryosu yaz:

SORU: {question['soru']}
KATEGORİ: {question['kategori']}
KARAKTER: {character} — {char_config.get('description', '')}
HOOK (ekranda gösterilecek metin): {question['hook']}
KOMİK POTANSİYEL: {question['komik_potansiyel']}/5

Çıktıyı TAM OLARAK bu JSON formatında ver (başka açıklama ekleme):
{{
  "scenes": [
    {{
      "id": "hook",
      "duration_seconds": 2,
      "description_tr": "Türkçe sahne açıklaması",
      "on_screen_text": "{question['hook']}",
      "character_action_tr": "Karakterin ne yaptığı (Türkçe)"
    }},
    {{
      "id": "main",
      "duration_seconds": 4,
      "description_tr": "Türkçe sahne açıklaması",
      "on_screen_text": "",
      "character_action_tr": "Karakterin ne yaptığı (Türkçe)"
    }},
    {{
      "id": "punchline",
      "duration_seconds": 2,
      "description_tr": "Türkçe sahne açıklaması",
      "on_screen_text": "Punch line metni (max 8 kelime)",
      "character_action_tr": "Karakterin ne yaptığı (Türkçe)"
    }}
  ],
  "veo_prompts": [
    {{
      "scene_id": "hook",
      "prompt": "Veo 3.1 İngilizce prompt (2 saniye için)"
    }},
    {{
      "scene_id": "main",
      "prompt": "Veo 3.1 İngilizce prompt (4 saniye için)"
    }},
    {{
      "scene_id": "punchline",
      "prompt": "Veo 3.1 İngilizce prompt (2 saniye için)"
    }}
  ],
  "audio_direction": {{
    "music_mood": "upbeat/funny/dramatic",
    "sound_effects": ["ses efekti 1", "ses efekti 2"],
    "character_voice_tr": "Karakterin punch line'da söyleyeceği söz (Türkçe)"
  }}
}}
"""

    logger.info(f"Soru {question['id']} için senaryo üretiliyor...")
    response = model.generate_content(user_prompt)
    raw = response.text.strip()

    # JSON bloğu varsa çıkar
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()

    script_data = json.loads(raw)
    script_data["metadata"] = {
        "question_id": question["id"],
        "soru": question["soru"],
        "kategori": question["kategori"],
        "karakter": character,
        "reels_caption": question["reels_caption"],
        "hashtags": question["hashtags"],
        "video_format": {
            "width": int(os.getenv("VIDEO_WIDTH", 1080)),
            "height": int(os.getenv("VIDEO_HEIGHT", 1920)),
            "duration_seconds": SCENE_TOTAL,
            "fps": int(os.getenv("VIDEO_FPS", 24)),
        },
    }

    output_path = SCRIPTS_DIR / f"script_q{question['id']:02d}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(script_data, f, ensure_ascii=False, indent=2)

    logger.success(f"Senaryo kaydedildi: {output_path}")
    return script_data

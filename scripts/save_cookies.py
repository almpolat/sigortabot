"""
Google Flow oturumu için cookie kaydedici.
Playwright ile gerçek tarayıcı açar, kullanıcı Google ile giriş yapar,
labs.google/fx/tr/tools/flow adresine gidildikten sonra cookies.json kaydeder.

YEREL MAKİNEDE ÇALIŞTIRIN:
    pip install playwright
    playwright install chromium
    python scripts/save_cookies.py

Kaydedilen cookies.json'u projenin kök dizinine kopyalayın.
"""

import json
import os
import sys
from pathlib import Path

FLOW_URL = "https://labs.google/fx/tr/tools/flow"
GOOGLE_LOGIN_URL = "https://accounts.google.com"
COOKIES_PATH = Path(__file__).parent.parent / "cookies.json"

# Ortama göre Chromium yolu — uzak sunucuda /opt/pw-browsers, yerelde otomatik
REMOTE_CHROMIUM = "/opt/pw-browsers/chromium"


def detect_environment() -> dict:
    """Çalışma ortamını tespit eder."""
    is_remote = Path(REMOTE_CHROMIUM).exists()
    has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    return {"is_remote": is_remote, "has_display": has_display}


def main():
    print("=" * 55)
    print("  SigortaBot — Google Flow Cookie Kaydedici")
    print("=" * 55)
    print()

    env = detect_environment()

    if env["is_remote"] and not env["has_display"]:
        print("  HATA: Bu script uzak sunucuda grafik ekran olmadan")
        print("  çalıştırılamaz. Lütfen YEREL makinenizde çalıştırın:")
        print()
        print("    1. Yerel makinenizde bu repoyu klonlayın veya")
        print("       sadece scripts/save_cookies.py dosyasını indirin.")
        print()
        print("    2. Gerekli paketleri yükleyin:")
        print("       pip install playwright")
        print("       playwright install chromium")
        print()
        print("    3. Scripti çalıştırın:")
        print("       python scripts/save_cookies.py")
        print()
        print("    4. Üretilen cookies.json dosyasını projenin")
        print("       kök dizinine kopyalayın.")
        sys.exit(1)

    from playwright.sync_api import sync_playwright

    # Chromium yolunu belirle
    launch_kwargs = {"headless": False, "args": ["--start-maximized"]}
    if Path(REMOTE_CHROMIUM).exists():
        launch_kwargs["executable_path"] = REMOTE_CHROMIUM

    with sync_playwright() as p:
        browser = p.chromium.launch(**launch_kwargs)
        context = browser.new_context(
            viewport=None,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        print("[1/3] Google hesabı giriş sayfasına gidiliyor...")
        page.goto(GOOGLE_LOGIN_URL, wait_until="domcontentloaded")

        print("[2/3] Lütfen Google hesabınıza giriş yapın.")
        print("      Giriş tamamlandıktan sonra bu script otomatik devam eder.")
        print("      (3 dakika zaman aşımı)")
        print()

        # Kullanıcı giriş yapana kadar bekle (myaccount.google.com'a yönlenince tamam)
        try:
            page.wait_for_url("**/myaccount.google.com/**", timeout=180_000)
        except Exception:
            # Bazen başka bir Google sayfasına yönlenebilir, cookie kontrolü yap
            cookies = context.cookies()
            google_cookies = [c for c in cookies if "google" in c.get("domain", "")]
            if not google_cookies:
                print("  HATA: Giriş 3 dakika içinde tamamlanamadı.")
                browser.close()
                sys.exit(1)

        print("      Giriş algılandı!")
        print()

        print(f"[3/3] Flow sayfasına gidiliyor...")
        print(f"      {FLOW_URL}")
        page.goto(FLOW_URL, wait_until="networkidle", timeout=60_000)

        # Sayfanın tam yüklenmesi için kısa bekleme
        page.wait_for_timeout(2000)

        cookies = context.cookies()

        with open(COOKIES_PATH, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)

        google_count = sum(1 for c in cookies if "google" in c.get("domain", ""))

        print()
        print(f"  Toplam cookie   : {len(cookies)}")
        print(f"  Google cookie   : {google_count}")
        print(f"  Kaydedilen yol  : {COOKIES_PATH}")
        print()
        print("  cookies.json hazir! Tarayici kapatiliyor.")

        browser.close()


if __name__ == "__main__":
    main()

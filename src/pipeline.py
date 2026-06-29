"""Ana pipeline: soru seç → senaryo üret → video oluştur."""

import json
from pathlib import Path
from typing import Optional

from loguru import logger
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from .question_picker import pick_questions
from .script_generator import generate_video_script
from .video_generator import generate_full_video

console = Console()
OUTPUT_DIR = Path(__file__).parent.parent / "output"


def run_pipeline(
    n: int = 5,
    kategori: Optional[str] = None,
    min_komik: int = 3,
    dry_run: bool = False,
    seed: Optional[int] = None,
) -> list[dict]:
    """
    Tam otonom pipeline: soru seç → senaryo üret → video üret.

    dry_run=True: Video üretimi atlanır, sadece senaryo üretilir.
    Döndürür: her video için sonuç bilgisi içeren liste.
    """
    console.rule("[bold cyan]SigortaBot Pipeline Başlıyor[/bold cyan]")

    questions = pick_questions(n=n, kategori=kategori, min_komik=min_komik, seed=seed)
    console.print(f"[green]{len(questions)} soru seçildi.[/green]")

    _print_question_table(questions)

    results = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        for q in questions:
            task = progress.add_task(f"Soru {q['id']}: {q['soru'][:50]}...", total=2)

            # Senaryo üret
            progress.update(task, description=f"[{q['id']}] Senaryo üretiliyor...")
            try:
                script = generate_video_script(q)
                progress.advance(task)
            except Exception as e:
                logger.error(f"Soru {q['id']} senaryo hatası: {e}")
                results.append({"question_id": q["id"], "status": "script_error", "error": str(e)})
                continue

            if dry_run:
                progress.advance(task)
                results.append({"question_id": q["id"], "status": "dry_run", "script": script})
                console.print(f"[yellow][DRY RUN] Soru {q['id']} senaryosu hazır, video atlandı.[/yellow]")
                continue

            # Video üret
            progress.update(task, description=f"[{q['id']}] Video üretiliyor...")
            try:
                video_path = generate_full_video(script)
                progress.advance(task)
                results.append({
                    "question_id": q["id"],
                    "status": "success",
                    "video_path": str(video_path),
                    "reels_caption": q["reels_caption"],
                    "hashtags": q["hashtags"],
                })
                console.print(f"[green]✓ Soru {q['id']} tamamlandı: {video_path.name}[/green]")
            except Exception as e:
                logger.error(f"Soru {q['id']} video hatası: {e}")
                results.append({"question_id": q["id"], "status": "video_error", "error": str(e)})

    _save_run_report(results)
    _print_summary(results)
    return results


def _print_question_table(questions: list[dict]) -> None:
    table = Table(title="Seçilen Sorular", show_header=True)
    table.add_column("ID", style="dim", width=4)
    table.add_column("Soru", style="cyan")
    table.add_column("Kategori", style="magenta")
    table.add_column("Karakter", style="green")
    table.add_column("Komik", justify="center")

    for q in questions:
        table.add_row(
            str(q["id"]),
            q["soru"][:60],
            q["kategori"],
            q["en_uygun_karakter"],
            "⭐" * q["komik_potansiyel"],
        )
    console.print(table)


def _save_run_report(results: list[dict]) -> None:
    report_path = OUTPUT_DIR / "last_run_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    logger.info(f"Run raporu kaydedildi: {report_path}")


def _print_summary(results: list[dict]) -> None:
    success = sum(1 for r in results if r["status"] == "success")
    dry = sum(1 for r in results if r["status"] == "dry_run")
    errors = len(results) - success - dry

    console.rule("[bold]Özet[/bold]")
    console.print(f"[green]Başarılı:[/green] {success}")
    if dry:
        console.print(f"[yellow]Dry run:[/yellow] {dry}")
    if errors:
        console.print(f"[red]Hata:[/red] {errors}")

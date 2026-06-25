"""SigortaBot CLI giriş noktası."""

from typing import Optional

import typer
from rich.console import Console

from .pipeline import run_pipeline
from .question_picker import get_categories, load_questions

app = typer.Typer(
    name="sigortabot",
    help="Türk sigorta sorularından komik AI animasyon videoları üretir.",
    add_completion=False,
)
console = Console()


@app.command()
def run(
    n: int = typer.Option(5, "--n", "-n", help="Üretilecek video sayısı"),
    kategori: Optional[str] = typer.Option(None, "--kategori", "-k", help="Sigorta kategorisi filtresi"),
    min_komik: int = typer.Option(3, "--min-komik", help="Minimum komik potansiyel (1-5)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Sadece senaryo üret, video atla"),
    seed: Optional[int] = typer.Option(None, "--seed", help="Tekrarlanabilirlik için seed"),
):
    """Video pipeline'ını çalıştırır."""
    if kategori:
        valid_cats = get_categories()
        if kategori not in valid_cats:
            console.print(f"[red]Geçersiz kategori: {kategori}[/red]")
            console.print(f"Geçerli kategoriler: {', '.join(sorted(valid_cats))}")
            raise typer.Exit(1)

    run_pipeline(n=n, kategori=kategori, min_komik=min_komik, dry_run=dry_run, seed=seed)


@app.command()
def list_questions(
    kategori: Optional[str] = typer.Option(None, "--kategori", "-k"),
    min_komik: int = typer.Option(1, "--min-komik"),
):
    """Mevcut soruları listeler."""
    from rich.table import Table

    questions = load_questions()
    if kategori:
        questions = [q for q in questions if q["kategori"] == kategori]
    questions = [q for q in questions if q["komik_potansiyel"] >= min_komik]

    table = Table(title=f"Sorular ({len(questions)} adet)")
    table.add_column("ID", width=4)
    table.add_column("Soru")
    table.add_column("Kategori")
    table.add_column("Karakter")
    table.add_column("Komik")

    for q in questions:
        table.add_row(
            str(q["id"]),
            q["soru"],
            q["kategori"],
            q["en_uygun_karakter"],
            "★" * q["komik_potansiyel"],
        )
    console.print(table)


@app.command()
def categories():
    """Mevcut kategorileri listeler."""
    cats = get_categories()
    for cat in sorted(cats):
        console.print(f"  • {cat}")


if __name__ == "__main__":
    app()

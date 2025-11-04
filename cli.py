import typer
from agent.core import run_pipeline

app = typer.Typer(add_completion=False)

@app.command()
def run(pipeline: str = "pipelines/example.yml"):
    """Run YAML pipeline end-to-end."""
    run_pipeline(pipeline)
    typer.echo("✅ Pipeline finished")

def main():
    app()

if __name__ == "__main__":
    main()

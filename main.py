import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
import typer
from agent.core import run_pipeline

app = typer.Typer(add_completion=False)

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context,
         pipeline: str = typer.Option("pipelines/example.yml", "--pipeline", "-p",
                                      help="Path to YAML pipeline")):
    # Если команду не указали — запускаем сразу
    if ctx.invoked_subcommand is None:
        run_pipeline(pipeline)
        typer.echo("Pipeline finished (OK)")

@app.command()
def run(pipeline: str = typer.Option("pipelines/example.yml", "--pipeline", "-p",
                                     help="Path to YAML pipeline")):
    run_pipeline(pipeline)
    typer.echo("Pipeline finished (OK)")

if __name__ == "__main__":
    app()


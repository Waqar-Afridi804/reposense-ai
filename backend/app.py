import os
from pathlib import Path
from alembic import command
from alembic.config import Config
import gradio as gr
import uvicorn

from app.main import app as fastapi_app


def run_migrations() -> None:
    """Apply pending Alembic database migrations before serving traffic."""
    ini_path = Path(__file__).resolve().parent / "alembic.ini"
    if ini_path.exists():
        alembic_cfg = Config(str(ini_path))
        command.upgrade(alembic_cfg, "head")


with gr.Blocks(title="RepoSense AI Backend") as demo:
    gr.Markdown("# RepoSense AI Backend\nFastAPI + pgvector + Gemini RAG service is running on `/api/*` and `/health`.")

try:
    import spaces

    @spaces.GPU
    def _zero_gpu_warmup():
        return "ready"
except Exception:
    pass

app = gr.mount_gradio_app(fastapi_app, demo, path="/ui")


if __name__ == "__main__":
    run_migrations()
    port = int(os.environ.get("PORT", "7860"))
    uvicorn.run(app, host="0.0.0.0", port=port)

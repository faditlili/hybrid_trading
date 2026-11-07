"""Public read-only Gradio dashboard. No username/password prompt by design."""
import os, requests, gradio as gr
API_PORT=os.getenv("PORT","7860")
API_URL=os.getenv("API_URL",f"http://127.0.0.1:{API_PORT}").rstrip("/")

def fetch(path):
    try:
        r=requests.get(API_URL+path,timeout=8); r.raise_for_status(); data=r.json()
        return data if isinstance(data,list) else data
    except Exception as e: return {"dashboard_error":str(e)}

def build_dashboard():
    with gr.Blocks(title="AI QUANT 4.0") as app:
        gr.Markdown("# AI QUANT 4.0\n**Paper simulation only — no real orders.**")
        status=gr.JSON(label="Portfolio status")
        positions=gr.JSON(label="Open simulated positions")
        trades=gr.JSON(label="Recent simulated trades")
        decisions=gr.JSON(label="Recent decisions")
        refresh=gr.Button("Refresh")
        refresh.click(lambda:(fetch("/dashboard/status"),fetch("/dashboard/positions"),fetch("/dashboard/trades"),fetch("/dashboard/decisions")),outputs=[status,positions,trades,decisions])
        app.load(lambda:(fetch("/dashboard/status"),fetch("/dashboard/positions"),fetch("/dashboard/trades"),fetch("/dashboard/decisions")),outputs=[status,positions,trades,decisions])
    return app

import gradio as gr
from app import logger
from gradio_ui import RAGGradioUI

logger.info("Starting Gradio frontend...")
try:
    from gradio_ui import RAGGradioUI
    ui = RAGGradioUI()
    demo = ui.create_interface()

    logger.info("🎉 Launching Gradio UI on port 7860...")
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        debug=False,
        show_error=True,
        show_api=False,
        quiet=False,
        inbrowser=True
    )

except Exception as e:
    logger.error(f"Failed to start Gradio: {e}")
    fastapi_process.terminate()
    sys.exit(1)
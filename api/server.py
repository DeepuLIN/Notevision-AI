import os
import base64
from pathlib import Path

import fitz  # PyMuPDF
from fastapi import FastAPI, File, UploadFile, Depends
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi_clerk_auth import (
    ClerkConfig,
    ClerkHTTPBearer,
    HTTPAuthorizationCredentials,
)
from openai import OpenAI

app = FastAPI()

# CORS for local Docker/dev.
# If frontend and backend are served from same container, this is not critical,
# but it does not hurt for local testing.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Clerk authentication
clerk_config = ClerkConfig(jwks_url=os.getenv("CLERK_JWKS_URL"))
clerk_guard = ClerkHTTPBearer(clerk_config)


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "NoteVision AI"}


@app.post("/api")
async def extract_text(
    file: UploadFile = File(...),
    creds: HTTPAuthorizationCredentials = Depends(clerk_guard),
):
    try:
        user_id = creds.decoded["sub"]
        print(f"NoteVision OCR request from user: {user_id}")

        key = os.getenv("OPEN_ROUTER_API_KEY")

        if not key:
            return JSONResponse(
                status_code=500,
                content={"error": "OPEN_ROUTER_API_KEY is missing"},
            )

        file_bytes = await file.read()

        if not file_bytes:
            return JSONResponse(
                status_code=400,
                content={"error": "No file uploaded"},
            )

        content_items = [
            {
                "type": "text",
                "text": (
                    "Extract all handwritten or printed text from this file. "
                    "Return only the extracted text. "
                    "Preserve line breaks where possible."
                ),
            }
        ]

        if file.content_type == "application/pdf":
            pdf = fitz.open(stream=file_bytes, filetype="pdf")

            # Safety limit for now, so huge PDFs do not crash the container.
            max_pages = int(os.getenv("MAX_PDF_PAGES", "10"))

            for page_index, page in enumerate(pdf):
                if page_index >= max_pages:
                    break

                pix = page.get_pixmap(dpi=200)
                image_bytes = pix.tobytes("png")
                image_base64 = base64.b64encode(image_bytes).decode("utf-8")

                content_items.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}"
                        },
                    }
                )

            pdf.close()

        else:
            content_type = file.content_type or "image/jpeg"
            image_base64 = base64.b64encode(file_bytes).decode("utf-8")

            content_items.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{content_type};base64,{image_base64}"
                    },
                }
            )

        client = OpenAI(
            api_key=key,
            base_url="https://openrouter.ai/api/v1",
            timeout=60,
        )

        stream = client.chat.completions.create(
            model="qwen/qwen2.5-vl-72b-instruct",
            stream=True,
            max_tokens=3000,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are NoteVision AI. Extract handwritten and printed "
                        "notes accurately from images or PDF pages. Return only "
                        "the extracted text."
                    ),
                },
                {
                    "role": "user",
                    "content": content_items,
                },
            ],
        )

        def generate():
            for chunk in stream:
                text = chunk.choices[0].delta.content
                if text:
                    yield text

        return StreamingResponse(generate(), media_type="text/plain")

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
        )


# Serve static files from exported Next.js build.
# This must stay LAST, otherwise it can swallow API routes.
static_path = Path("static")

if static_path.exists():

    @app.get("/")
    async def serve_root():
        return FileResponse(static_path / "index.html")

    app.mount("/", StaticFiles(directory="static", html=True), name="static")
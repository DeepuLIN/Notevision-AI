import os
import base64
import fitz  # PyMuPDF

from fastapi import FastAPI, File, UploadFile, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi_clerk_auth import (
    ClerkConfig,
    ClerkHTTPBearer,
    HTTPAuthorizationCredentials,
)
from openai import OpenAI

app = FastAPI()

clerk_config = ClerkConfig(jwks_url=os.getenv("CLERK_JWKS_URL"))
clerk_guard = ClerkHTTPBearer(clerk_config)


@app.get("/")
@app.get("/api")
async def health_check():
    return {"status": "NoteVision API is running"}


@app.post("/")
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

            for page in pdf:
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
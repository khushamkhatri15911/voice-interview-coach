import io
import os
import re
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from livekit import api
from pydantic import BaseModel, Field
from pypdf import PdfReader

from db import get_history, get_report_payload, save_context

load_dotenv()

app = FastAPI(title="Voice Interview Coach API")

# Allow our React app (it runs on port 5173) to call this server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

INTERVIEW_TYPES = ("behavioural", "technical", "mixed")
CLIENT_ID_PATTERN = re.compile(r"[A-Za-z0-9-]{8,64}")
MAX_UPLOAD_BYTES = 2 * 1024 * 1024


class TokenRequest(BaseModel):
    role: str = "Junior Data Analyst"
    interview_type: str = "behavioural"
    client_id: str | None = None
    resume_text: str = Field(default="", max_length=30000)
    job_description: str = Field(default="", max_length=30000)


@app.post("/token")
def create_token(req: TokenRequest):
    if req.interview_type not in INTERVIEW_TYPES:
        raise HTTPException(status_code=400, detail="Invalid interview type")

    role = req.role.strip()[:60] or "Junior Data Analyst"
    room_name = f"interview-{uuid.uuid4().hex[:8]}"
    identity = f"candidate-{uuid.uuid4().hex[:8]}"

    attributes = {"role": role, "interview_type": req.interview_type}
    if req.client_id and CLIENT_ID_PATTERN.fullmatch(req.client_id):
        attributes["client_id"] = req.client_id

    resume = req.resume_text.strip()[:6000]
    job = req.job_description.strip()[:4000]
    if resume or job:
        attributes["context_id"] = save_context(resume, job)

    token = (
        api.AccessToken(os.environ["LIVEKIT_API_KEY"], os.environ["LIVEKIT_API_SECRET"])
        .with_identity(identity)
        .with_name("Candidate")
        .with_grants(api.VideoGrants(room_join=True, room=room_name))
        .with_attributes(attributes)
        .to_jwt()
    )

    return {
        "serverUrl": os.environ["LIVEKIT_URL"],
        "roomName": room_name,
        "participantToken": token,
    }


@app.post("/extract-resume")
async def extract_resume(file: UploadFile = File(...)):
    name = (file.filename or "").lower()
    if not name.endswith((".pdf", ".txt")):
        raise HTTPException(status_code=400, detail="Please upload a PDF or TXT file")

    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is too large (2 MB maximum)")

    try:
        if name.endswith(".pdf"):
            reader = PdfReader(io.BytesIO(data))
            text = "\n".join((page.extract_text() or "") for page in reader.pages[:5])
        else:
            text = data.decode("utf-8", errors="ignore")
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read this file")

    text = text.strip()
    if not text:
        raise HTTPException(
            status_code=400,
            detail="No text found in the file. If it is a scan, paste the text instead.",
        )
    return {"text": text[:20000]}


@app.get("/report/{room_name}")
def get_report(room_name: str):
    if not re.fullmatch(r"interview-[0-9a-f]{8}", room_name):
        raise HTTPException(status_code=400, detail="Invalid room name")
    payload = get_report_payload(room_name)
    if payload is None:
        raise HTTPException(status_code=404, detail="Report not ready yet")
    return payload


@app.get("/history")
def history(client_id: str):
    if not CLIENT_ID_PATTERN.fullmatch(client_id):
        raise HTTPException(status_code=400, detail="Invalid client id")
    return get_history(client_id)
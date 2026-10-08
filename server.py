import os
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from livekit import api
from pydantic import BaseModel

load_dotenv()

app = FastAPI(title="Voice Interview Coach API")

# Allow our React app (it will run on port 5173) to call this server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

INTERVIEW_TYPES = ("behavioural", "technical", "mixed")


class TokenRequest(BaseModel):
    role: str = "Junior Data Analyst"
    interview_type: str = "behavioural"


@app.post("/token")
def create_token(req: TokenRequest):
    if req.interview_type not in INTERVIEW_TYPES:
        raise HTTPException(status_code=400, detail="Invalid interview type")

    role = req.role.strip()[:60] or "Junior Data Analyst"
    room_name = f"interview-{uuid.uuid4().hex[:8]}"
    identity = f"candidate-{uuid.uuid4().hex[:8]}"

    token = (
        api.AccessToken(os.environ["LIVEKIT_API_KEY"], os.environ["LIVEKIT_API_SECRET"])
        .with_identity(identity)
        .with_name("Candidate")
        .with_grants(api.VideoGrants(room_join=True, room=room_name))
        .with_attributes({"role": role, "interview_type": req.interview_type})
        .to_jwt()
    )

    return {
        "serverUrl": os.environ["LIVEKIT_URL"],
        "roomName": room_name,
        "participantToken": token,
    }
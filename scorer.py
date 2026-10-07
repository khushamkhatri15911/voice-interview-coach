import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

load_dotenv()

MODEL = "openai/gpt-oss-20b"  # try "openai/gpt-oss-120b" for more careful scoring
TRANSCRIPT_DIR = Path(__file__).parent / "transcripts"
REPORT_DIR = Path(__file__).parent / "reports"
REPORT_DIR.mkdir(exist_ok=True)


class QuestionFeedback(BaseModel):
    question: str
    answer_summary: str
    score: int = Field(ge=1, le=10)
    what_was_good: str
    what_to_improve: str
    better_answer_tip: str


class InterviewReport(BaseModel):
    overall_score: int = Field(ge=1, le=10)
    clarity: int = Field(ge=1, le=10)
    structure: int = Field(ge=1, le=10)
    specificity: int = Field(ge=1, le=10)
    technical_depth: int = Field(ge=1, le=10)
    strengths: list[str]
    weaknesses: list[str]
    per_question: list[QuestionFeedback]
    next_steps: list[str]


SYSTEM_PROMPT = f"""
You are a strict but fair interview coach. You will receive the transcript of a mock
job interview between an Interviewer and a Candidate.

Score ONLY what the candidate actually said. Never invent details. Do not reward
answers for length alone. The transcript comes from speech-to-text, so ignore small
transcription errors and stumbles.

Scoring guide (1 to 10):
- clarity: is the answer easy to follow and on topic?
- structure: for behavioural answers, does it cover the Situation, the candidate's own
  Action, and the Result (STAR)? For technical answers, is the explanation organised?
- specificity: does it include concrete details such as numbers, tools, and outcomes?
- technical_depth: is the content correct and deep enough for the role?
Short, vague answers must score low (1 to 4). Only clearly excellent answers score 9 or 10.

Give feedback only for questions the candidate actually answered. Skip any question
the candidate skipped or that was cut off.
Keep each text field to 1 or 2 sentences. Speak directly to the candidate ("you").

Reply with ONLY a JSON object matching this schema, and nothing else:
{json.dumps(InterviewReport.model_json_schema())}
"""


def pick_transcript() -> Path:
    if len(sys.argv) > 1:
        return Path(sys.argv[1])
    files = sorted(TRANSCRIPT_DIR.glob("transcript_*.json"))
    if not files:
        sys.exit("No transcripts found. Run an interview first.")
    return files[-1]


def transcript_to_text(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    lines = []
    for item in data["items"]:
        if item.get("type") != "message":
            continue
        speaker = "Interviewer" if item["role"] == "assistant" else "Candidate"
        text = " ".join(c for c in item.get("content", []) if isinstance(c, str)).strip()
        if text:
            lines.append(f"{speaker}: {text}")
    return "\n".join(lines)


def score(transcript: str) -> InterviewReport:
    client = OpenAI(
        api_key=os.environ["GROQ_API_KEY"],
        base_url="https://api.groq.com/openai/v1",
    )
    last_error = None
    for attempt in range(2):
        response = client.chat.completions.create(
            model=MODEL,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": transcript},
            ],
        )
        raw = response.choices[0].message.content
        try:
            return InterviewReport.model_validate_json(raw)
        except ValidationError as e:
            last_error = e
            print(f"Attempt {attempt + 1}: the AI's reply was not valid, retrying...")
        raise RuntimeError(f"Could not get a valid report: {last_error}")


def print_report(r: InterviewReport) -> None:
    print("\n========== INTERVIEW REPORT ==========")
    print(f"Overall: {r.overall_score}/10")
    print(f"Clarity: {r.clarity}   Structure: {r.structure}   "
          f"Specificity: {r.specificity}   Technical depth: {r.technical_depth}")
    print("\nStrengths:")
    for s in r.strengths:
        print(f"  + {s}")
    print("\nWeaknesses:")
    for w in r.weaknesses:
        print(f"  - {w}")
    print("\nPer question:")
    for q in r.per_question:
        print(f"\n  Q: {q.question}  [{q.score}/10]")
        print(f"     Good: {q.what_was_good}")
        print(f"     Improve: {q.what_to_improve}")
        print(f"     Tip: {q.better_answer_tip}")
    print("\nNext steps:")
    for n in r.next_steps:
        print(f"  * {n}")
    print("======================================\n")


if __name__ == "__main__":
    path = pick_transcript()
    print(f"Scoring {path.name} ...")
    report = score(transcript_to_text(path))
    print_report(report)
    out = REPORT_DIR / f"report_{path.stem.replace('transcript_', '')}.json"
    out.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    print(f"Report saved to {out}")
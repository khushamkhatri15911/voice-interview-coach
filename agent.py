import asyncio
import json
from datetime import datetime
from pathlib import Path
from db import save_interview

from dotenv import load_dotenv
from livekit import agents
from livekit.agents import Agent, AgentSession, ChatContext, ChatMessage, StopResponse
from livekit.plugins import deepgram, groq, silero
from scorer import REPORT_DIR, print_report, score, transcript_to_text

load_dotenv()

# ---- Interview settings (we will make these selectable in the web app later) ----
ROLE = "Junior Data Analyst"
INTERVIEW_TYPE = "behavioural"  # behavioural, technical, or mixed
MAX_FOLLOWUPS = 1  # follow-up questions allowed per main question (0 = none)

TRANSCRIPT_DIR = Path(__file__).parent / "transcripts"
TRANSCRIPT_DIR.mkdir(exist_ok=True)

BEHAVIOURAL = [
    "Tell me about a time you used data to solve a real problem.",
    "Describe a time you had to explain complex findings to someone non-technical.",
    "Tell me about a time you worked under a tight deadline.",
    "Describe a time you found a mistake in your own work and how you handled it.",
    "Tell me about a time you worked in a team to deliver a project.",
]
TECHNICAL = [
    "What is the difference between an INNER JOIN and a LEFT JOIN in SQL?",
    "How would you handle missing values in a dataset?",
    "Explain the difference between correlation and causation.",
    "How would you check a dataset for outliers, and what would you do about them?",
    "Walk me through how you would build a simple dashboard for a business team.",
]
QUESTION_BANK = {
    "behavioural": BEHAVIOURAL,
    "technical": TECHNICAL,
    "mixed": [BEHAVIOURAL[0], TECHNICAL[0], BEHAVIOURAL[1], TECHNICAL[1], BEHAVIOURAL[2]],
}

REPEAT_PHRASES = ["repeat", "say that again", "say it again", "pardon", "didn't catch", "come again"]
SKIP_PHRASES = ["skip", "next question", "move on", "pass on this"]


class Interviewer(Agent):
    def __init__(self, role: str, interview_type: str, questions: list[str]):
        super().__init__(
            instructions=f"""
You are Alex, a friendly, professional interviewer hiring for a {role} position.
The interview type is: {interview_type}.
Before each of your replies you will receive an instruction about what to do next.
Follow the latest instruction exactly.

Always:
- Speak in 1 or 2 short sentences, because your words are spoken aloud.
- Never use lists, bullet points, markdown or emojis.
- Ask only ONE question per reply.
- Never mention or list future questions.
- Never give feedback or scores during the interview.
"""
        )
        self.questions = questions
        self.q_index = 0  # which main question we are on
        self.followups_used = 0
        self.finished = False

    def _next_main_question(self) -> str:
        self.q_index += 1
        self.followups_used = 0
        if self.q_index < len(self.questions):
            return (
                "Say a very short thanks (a few words), then ask this next question "
                f'word for word: "{self.questions[self.q_index]}"'
            )
        self.finished = True
        return (
            "That was the last question. Thank the candidate warmly in one or two "
            "sentences, say the interview is finished and their feedback will be "
            "ready shortly. Do not ask any more questions."
        )

    async def on_user_turn_completed(
        self, turn_ctx: ChatContext, new_message: ChatMessage
    ) -> None:
        if self.finished:
            raise StopResponse()  # interview is over, stay silent

        text = (new_message.text_content or "").lower()

        if any(p in text for p in REPEAT_PHRASES):
            instruction = (
                "The candidate asked you to repeat or clarify. Repeat your last "
                "question in one short sentence. Do not ask anything new."
            )
        elif any(p in text for p in SKIP_PHRASES) or self.followups_used >= MAX_FOLLOWUPS:
            instruction = self._next_main_question()
        else:
            self.followups_used += 1
            instruction = (
                "Say a very short acknowledgement, then ask exactly ONE short "
                "follow-up question about a specific detail the candidate just "
                "mentioned (a number, their own action, or the result). "
                "Do not ask a new main question."
            )

        turn_ctx.add_message(role="system", content=instruction)


async def entrypoint(ctx: agents.JobContext):
    await ctx.connect()
    participant = await ctx.wait_for_participant()
    role = participant.attributes.get("role", ROLE)
    interview_type = participant.attributes.get("interview_type", INTERVIEW_TYPE)
    if interview_type not in QUESTION_BANK:
        interview_type = INTERVIEW_TYPE
    print(f"Interview starting: {role} / {interview_type}")
    room_name = ctx.room.name

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=groq.LLM(model="openai/gpt-oss-20b"),
        tts=deepgram.TTS(),
        vad=silero.VAD.load(),
    )

    async def save_transcript():
        path = TRANSCRIPT_DIR / f"transcript_{room_name}.json"
        out = REPORT_DIR / f"report_{room_name}.json"
        history = session.history.to_dict()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
        print(f"Transcript saved to {path}")

        async def store(status, **fields):
            try:
                await asyncio.to_thread(
                    save_interview,
                    room_name=room_name,
                    role=role,
                    interview_type=interview_type,
                    transcript=history,
                    status=status,
                    **fields,
                )
                print("Saved to database")
            except Exception as e:
                print(f"Could not save to database: {e}")

        try:
            text = transcript_to_text(path)
            if text.count("Candidate:") < 2:
                msg = "Interview too short to score (you need to answer at least 2 questions)."
                print(msg)
                out.write_text(json.dumps({"error": msg}), encoding="utf-8")
                await store("too_short", error=msg)
                return
            print("Scoring your interview, please wait...")
            report = await asyncio.to_thread(score, text)
            print_report(report)
            out.write_text(report.model_dump_json(indent=2), encoding="utf-8")
            await store(
                "scored",
                overall_score=report.overall_score,
                clarity=report.clarity,
                structure=report.structure,
                specificity=report.specificity,
                technical_depth=report.technical_depth,
                report=report.model_dump(),
            )
        except Exception as e:
            print(f"Could not score this interview: {e}")
            msg = "Could not score this interview."
            out.write_text(json.dumps({"error": msg}), encoding="utf-8")
            await store("failed", error=msg)

    ctx.add_shutdown_callback(save_transcript)

    questions = QUESTION_BANK[interview_type]
    await session.start(
        room=ctx.room,
        agent=Interviewer(role, interview_type, questions),
    )
    await session.generate_reply(
        instructions=(
            f"Greet the candidate in one short sentence, say you will ask "
            f"{len(questions)} questions, then ask this first question word for word: "
            f'"{questions[0]}"'
        )
    )


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
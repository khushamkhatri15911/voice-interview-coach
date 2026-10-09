import { useState } from "react";
import {
  LiveKitRoom,
  RoomAudioRenderer,
  useVoiceAssistant,
  useLocalParticipant,
} from "@livekit/components-react";
import "@livekit/components-styles";
import { API_URL, getClientId } from "./api";
import { ReportLoader } from "./Report.jsx";
import HistoryScreen from "./History.jsx";

const INTERVIEW_TYPES = [
  { value: "behavioural", label: "Behavioural" },
  { value: "technical", label: "Technical" },
  { value: "mixed", label: "Mixed" },
];

export default function App() {
  const [role, setRole] = useState("Junior Data Analyst");
  const [interviewType, setInterviewType] = useState("behavioural");
  const [connection, setConnection] = useState(null);
  const [roomName, setRoomName] = useState(null);
  const [pastRoom, setPastRoom] = useState(null);
  const [phase, setPhase] = useState("setup"); // setup | live | scoring | history | past
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function startInterview() {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_URL}/token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          role,
          interview_type: interviewType,
          client_id: getClientId(),
        }),
      });
      if (!res.ok) throw new Error(`server answered ${res.status}`);
      const data = await res.json();
      setConnection({ serverUrl: data.serverUrl, token: data.participantToken });
      setRoomName(data.roomName);
      setPhase("live");
    } catch (e) {
      setError(`Could not start the interview. Is the FastAPI server running? (${e.message})`);
    } finally {
      setLoading(false);
    }
  }

  function endInterview() {
    setPhase((p) => (p === "live" ? "scoring" : p));
    setConnection(null);
  }

  function goHome() {
    setRoomName(null);
    setPhase("setup");
  }

  if (phase === "scoring") {
    return <ReportLoader roomName={roomName} onBack={goHome} backLabel="Practice again" fresh />;
  }

  if (phase === "history") {
    return (
      <HistoryScreen
        onBack={goHome}
        onOpen={(room) => {
          setPastRoom(room);
          setPhase("past");
        }}
      />
    );
  }

  if (phase === "past") {
    return (
      <ReportLoader
        roomName={pastRoom}
        onBack={() => setPhase("history")}
        backLabel="Back to history"
        fresh={false}
      />
    );
  }

  if (phase === "setup") {
    return (
      <div className="card narrow">
        <h1>Voice Interview Coach</h1>
        <p className="sub">Practice a real spoken interview and get scored feedback.</p>

        <label htmlFor="role">Job role</label>
        <input
          id="role"
          type="text"
          value={role}
          maxLength={60}
          onChange={(e) => setRole(e.target.value)}
        />

        <label>Interview type</label>
        <div className="types">
          {INTERVIEW_TYPES.map((t) => (
            <button
              key={t.value}
              className={interviewType === t.value ? "active" : ""}
              onClick={() => setInterviewType(t.value)}
            >
              {t.label}
            </button>
          ))}
        </div>

        <button className="primary" onClick={startInterview} disabled={loading || !role.trim()}>
          {loading ? "Starting..." : "Start interview"}
        </button>
        <button className="secondary" onClick={() => setPhase("history")}>
          View my progress
        </button>
        {error && <p className="error">{error}</p>}
        <p className="tip">Use headphones so the interviewer doesn't hear itself.</p>
      </div>
    );
  }

  return (
    <LiveKitRoom
      serverUrl={connection.serverUrl}
      token={connection.token}
      connect={true}
      audio={true}
      video={false}
      onDisconnected={endInterview}
    >
      <InterviewScreen role={role} interviewType={interviewType} onEnd={endInterview} />
      <RoomAudioRenderer />
    </LiveKitRoom>
  );
}

const STATUS_LABELS = {
  connecting: "Connecting...",
  initializing: "Alex is getting ready...",
  listening: "Listening to you",
  thinking: "Thinking...",
  speaking: "Alex is speaking",
  disconnected: "Disconnected",
};

function InterviewScreen({ role, interviewType, onEnd }) {
  const { state } = useVoiceAssistant();
  const { localParticipant, isMicrophoneEnabled } = useLocalParticipant();

  return (
    <div className="card narrow">
      <h1>Interview in progress</h1>
      <p className="meta">
        {role} · {interviewType}
      </p>

      <div className={`orb ${state}`} />
      <div className="status">{STATUS_LABELS[state] || state}</div>

      <button
        className="secondary"
        onClick={() => localParticipant.setMicrophoneEnabled(!isMicrophoneEnabled)}
      >
        {isMicrophoneEnabled ? "Mute microphone" : "Unmute microphone"}
      </button>
      <button className="danger" onClick={onEnd}>
        End interview
      </button>
    </div>
  );
}
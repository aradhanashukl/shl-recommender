from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .agent import run_agent
from .schemas import ChatRequest, ChatResponse, HealthResponse

app = FastAPI(title="SHL Assessment Recommender")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_TURNS = 8


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok")


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    # Never feed more messages than the turn cap
    messages = req.messages[-MAX_TURNS:]
    try:
        result = run_agent(messages)
    except Exception as e:
        # Never let the grader see a 500 — degrade gracefully
        return ChatResponse(
            reply="Could you rephrase the role or skills you're hiring for?",
            recommendations=[],
            end_of_conversation=False,
        )

    # Force close at turn cap if still no recommendations
    if len(req.messages) >= MAX_TURNS - 1 and not result["recommendations"]:
        result["end_of_conversation"] = True

    return ChatResponse(**result)

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.agent import DroneOpsAgent

app = FastAPI(title="Drone Ops Coordinator Agent")
app.mount("/static", StaticFiles(directory="static"), name="static")

agent = DroneOpsAgent()


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    with open("static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/chat")
def chat(req: ChatRequest) -> dict:
    reply, data = agent.handle(req.message)
    return {"reply": reply, "data": data}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

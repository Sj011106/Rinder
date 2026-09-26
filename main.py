from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from chatbot import chat
from matching import get_suggested_roommates
from recommendations import get_recommended_listings

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    user_id: str
    message: str


@app.post("/chatbot")
def chatbot_endpoint(req: ChatRequest):
    answer = chat(req.user_id, req.message)
    return {"answer": answer}


@app.get("/roommates")
def roommates_endpoint(user_id: str):
    return get_suggested_roommates(user_id)

@app.get("/recommended-listings")
def recommended_listings_endpoint(user_id: str):
    return get_recommended_listings(user_id)
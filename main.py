from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
import re

app = FastAPI()

# Request/Response models

class ParseTextRequest(BaseModel):
    text: str
    setNumber: int

class ParsedEvent(BaseModel):
    setNumber: int
    playerNumber: Optional[int] #None for "point us / point them"
    event: str #"KILL", "DIG"
    pointAwardedTo: Optional[str] #"us", "them" or None for actions like "DIG" which dont award points
    needsReview: bool
    rawText:str

# Parsing rules for events

EVENT_MAP = {
    "kill": ("KILL", "us"),
    "dig": ("DIG", None),
    "hitting error":("HITTING_ERROR", "them"),
    "point us": ("POINT_US", "us"),
    "point them": ("POINT_THEM", "them")
}

def parse_command(text: str, setNumber: int):
    cleaned = text.strip().lower()

    # handle simple command "point us" or "point them"
    if cleaned in ("point us", "point them"):
        event, awarded = EVENT_MAP[cleaned]
        return {
            "setNumber": setNumber,
            "playerNumber": None,
            "event": event,
            "pointAwardedTo": awarded,
            "needsReview": False,
            "rawText": text
        }

    #extract player number
    m = re.search(r"\b(\d{1,2})\b", cleaned)
    player = int(m.group(1)) if m else None

    #find best matching event phrase 
    matched = None

    for phrase in sorted(EVENT_MAP.keys(), key=len, reverse=True):
        if phrase in cleaned and phrase not in ("point us", "point them"):
            matched = phrase
            break

    if player is None or matched is None:
        return {
            "setNumber": setNumber,
            "playerNumber": player,
            "event": "UNKNOWN",
            "pointAwardedTo": None,
            "needsReview": True,
            "rawText": text
        }
    
    event, awarded = EVENT_MAP[matched]
    return {
        "setNumber": setNumber,
        "playerNumber": player,
        "event": event,
        "pointAwardedTo": awarded,
        "needsReview": False,
        "rawText": text
    }


@app.get("/")
def root():
    return {"Hello": "World"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/parse-text", response_model=ParsedEvent)
def parse_text(request: ParseTextRequest):
    return parse_command(request.text, request.setNumber)


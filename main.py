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
    "serve": ("SERVE", None),
    "ace": ("ACE", "us"),
    "serve error": ("SERVE_ERROR", "them"),
    "hit attempt": ("HIT_ATTEMPT", None),
    "kill": ("KILL", "us"),
    "hit error":("HIT_ERROR", "them"),
    "good pass": ("GOOD_PASS", None),
    "bad pass": ("BAD_PASS", None),
    "pass error": ("PASS_ERROR", "them"),
    "block": ("BLOCK", "us"),
    "block assist": ("BLOCK_ASSIST", None),
    "block error": ("BLOCK_ERROR", "them"),
    "assist": ("ASSIST", None),
    "ball handling error": ("BALL_HANDLING_ERROR", "them"),
    "dig": ("DIG", None),
    "dig error": ("DIG_ERROR", "them"),
    "point us": ("POINT_US", "us"),
    "point them": ("POINT_THEM", "them"),
}

# Explicit synonym rules. Keep this small and intentional; expand from real usage.
SYNONYM_VERSION = "v1"
SYNONYM_RULES = {
    "v1": {
        "serve": [
            "served",
            "served the ball",
        ],
        "ace": [
            "got an ace",
            "aced them",
        ],
        "serve error": [
            "service error",
            "foot fault",
            "served in the net",
            "served out",
            "served long",
            "serve in the net",
        ],
        "hit attempt": [
            "hit attempt",
            "attack",
            "swing",
            "spike",
        ],
        "kill": [
            "got a kill",
            "gets a kill",
            "killed it",
        ],
        "hit error":[
            "hit error",
            "attack error",
            "missed hit",
            "hit in the net",
            "hit out",
            "tip error",
            "tipped it out",
            "tipped the ball out",
            "swung out",
        ],
        "good pass": [
            "nice pass",
            "pass",
            "solid pass",
            "dime",
            "dime pass",
            "perfect pass",
        ],
        "bad pass": [
            "bad pass",
            "poor pass",
            "weak pass",
        ],
        "pass error": [
            "got aced",
            "missed pass",
            "passing error",
        ],
        "block": [
            "got a block",
            "blocked it",
            "blocked the ball",
            "solo block",
        ],
        "block assist": [
            "got a block assist",
        ],
        "block error": [
            "missed block",
            "hit the net",
            "net violation",
            "net",
            "block in the net",
            "block out",
        ],
        "assist": [
            "got an assist",
        ],
        "ball handling error": [
            "double contact",
            "lift",
            "carry",
            "illegal contact",
        ],
        "dig": [
            "got a dig",
            "dug it",
            "dug the ball",
        ],
        "dig error": [
            "missed dig",
            "missed the dig",
        ],
        "point us": [
            "our point",
            "we got a point",
            "point for us",
            "point to us",
            "point us",
            "point for our team",
        ],
        "point them": [
            "their point",
            "they got a point",
            "point for them",
        ],
    }
}

def normalize_with_synonyms(text: str):
    cleaned = text.strip().lower()
    rules = SYNONYM_RULES.get(SYNONYM_VERSION, {})

    replacements = []
    for canonical, variants in rules.items():
        for variant in variants:
            replacements.append((variant, canonical))

    # Prefer more specific phrases first so "attack error" beats "attack".
    for variant, canonical in sorted(replacements, key=lambda item: len(item[0]), reverse=True):
        pattern = rf"\b{re.escape(variant)}\b"
        cleaned = re.sub(pattern, canonical, cleaned)

    return cleaned

def parse_command(text: str, setNumber: int):
    cleaned = normalize_with_synonyms(text)

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

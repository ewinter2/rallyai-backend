from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
from uuid import UUID
import os
import re

app = FastAPI()

# Request/Response models

class ParseTextRequest(BaseModel):
    text: str
    setNumber: int
    teamId: Optional[UUID] = None
    matchId: Optional[UUID] = None

class ParsedEvent(BaseModel):
    setNumber: int
    playerNumber: Optional[int] #None for "point us / point them"
    event: str #"KILL", "DIG"
    pointAwardedTo: Optional[str] #"us", "them" or None for actions like "DIG" which dont award points
    needsReview: bool
    rawText:str
    playerId: Optional[UUID] = None
    teamId: Optional[UUID] = None
    matchId: Optional[UUID] = None

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
            "serve",
            "served",
            "served the ball",
            "serves",
            "serving",
        ],
        "ace": [
            "ace",
            "got an ace",
            "aced them",
            "serves an ace",
            "served an ace",
            "service ace",
            "ace serve",
            "aced them",
        ],
        "serve error": [
            "serve error",
            "service error",
            "foot fault",
            "served in the net",
            "served out",
            "served long",
            "served in the net",
            "serving error",
            "missed serve",
        ],
        "hit attempt": [
            "hit",
            "hit attempt",
            "attack",
            "swing",
            "spike",
        ],
        "kill": [
            "kill",
            "got a kill",
            "gets a kill",
            "killed it",
            "got the kill",

        ],
        "hit error":[
            "hitting error",
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
            "good pass",
            "nice pass",
            "pass",
            "solid pass",
            "dime",
            "dime pass",
            "perfect pass",
            "great pass",
        ],
        "bad pass": [
            "bad pass",
            "poor pass",
            "weak pass",
            "shanked the pass",
            "shanke",
            "shanked",
        ],
        "pass error": [
            "pass error",
            "got aced",
            "missed pass",
            "passing error",
        ],
        "block": [
            "block",
            "got a block",
            "blocked it",
            "blocked the ball",
            "solo block",
            "stuffed",
            "stuff block",
        ],
        "block assist": [
            "block assist",
            "got a block assist",
        ],
        "block error": [
            "block error",
            "missed block",
            "hit the net",
            "net violation",
            "net",
            "block in the net",
            "block out",
        ],
        "assist": [
            "assist",
            "got an assist",
        ],
        "ball handling error": [
            "ball handling error",
            "double contact",
            "lift",
            "carry",
            "illegal contact",
        ],
        "dig": [
            "dig",
            "got a dig",
            "dug it",
            "dug the ball",
            "dug",
            "with the dig",
        ],
        "dig error": [
            "dig error",
            "missed dig",
            "missed the dig",
        ],
        "point us": [
            "point us",
            "our point",
            "we got a point",
            "point for us",
            "point to us",
            "point for our team",
            "side out",
            "we scored",
        ],
        "point them": [
            "point them",
            "their point",
            "they got a point",
            "point for them",
            "side out for them",
            "they scored",
        ],
    }
}

NUMBER_WORD_MAP = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13",
    "fourteen": "14", "fifteen": "15", "sixteen": "16", "seventeen": "17",
    "eighteen": "18", "nineteen": "19",
    "twenty": "20",
    "twenty one": "21", "twenty two": "22", "twenty three": "23",
    "twenty four": "24", "twenty five": "25", "twenty six": "26",
    "twenty seven": "27", "twenty eight": "28", "twenty nine": "29",
    "thirty": "30",
    "thirty one": "31", "thirty two": "32", "thirty three": "33",
    "thirty four": "34", "thirty five": "35", "thirty six": "36",
    "thirty seven": "37", "thirty eight": "38", "thirty nine": "39",
    "forty": "40",
    "forty one": "41", "forty two": "42", "forty three": "43",
    "forty four": "44", "forty five": "45", "forty six": "46",
    "forty seven": "47", "forty eight": "48", "forty nine": "49",
    "fifty": "50",
    "fifty one": "51", "fifty two": "52", "fifty three": "53",
    "fifty four": "54", "fifty five": "55", "fifty six": "56",
    "fifty seven": "57", "fifty eight": "58", "fifty nine": "59",
    "sixty": "60",
    "sixty one": "61", "sixty two": "62", "sixty three": "63",
    "sixty four": "64", "sixty five": "65", "sixty six": "66",
    "sixty seven": "67", "sixty eight": "68", "sixty nine": "69",
    "seventy": "70",
    "seventy one": "71", "seventy two": "72", "seventy three": "73",
    "seventy four": "74", "seventy five": "75", "seventy six": "76",
    "seventy seven": "77", "seventy eight": "78", "seventy nine": "79",
    "eighty": "80",
    "eighty one": "81", "eighty two": "82", "eighty three": "83",
    "eighty four": "84", "eighty five": "85", "eighty six": "86",
    "eighty seven": "87", "eighty eight": "88", "eighty nine": "89",
    "ninety": "90",
    "ninety one": "91", "ninety two": "92", "ninety three": "93",
    "ninety four": "94", "ninety five": "95", "ninety six": "96",
    "ninety seven": "97", "ninety eight": "98", "ninety nine": "99",
}

def preprocess_number_words(text: str) -> str:
    t = text.strip().lower()
    # Strip "number" used as a prefix keyword: "number seven" → "seven", "number 7" → "7"
    t = re.sub(r'\bnumber\b\s*', '', t)
    # Replace number words with digits, longest match first so "twenty one" beats "twenty"
    for word, digit in sorted(NUMBER_WORD_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        t = re.sub(rf'\b{re.escape(word)}\b', digit, t)
    return t

def normalize_with_synonyms(text: str):
    cleaned = preprocess_number_words(text)
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

def parse_command(
    text: str,
    setNumber: int,
    teamId: Optional[UUID] = None,
    matchId: Optional[UUID] = None
):
    cleaned = normalize_with_synonyms(text)

    # handle point events — no player number expected, match anywhere in the string
    for pt_phrase in ("point us", "point them"):
        if pt_phrase in cleaned:
            event, awarded = EVENT_MAP[pt_phrase]
            return {
                "setNumber": setNumber,
                "playerNumber": None,
                "event": event,
                "pointAwardedTo": awarded,
                "needsReview": False,
                "rawText": text,
                "playerId": None,
                "teamId": teamId,
                "matchId": matchId,
            }

    # extract all player numbers present in the command
    all_numbers = re.findall(r"\b(\d{1,2})\b", cleaned)
    player = int(all_numbers[0]) if all_numbers else None

    # block assist: two players + a block = block assist
    if len(all_numbers) >= 2 and re.search(r"\bblock\b", cleaned):
        event, awarded = EVENT_MAP["block assist"]
        return {
            "setNumber": setNumber,
            "playerNumber": player,
            "event": event,
            "pointAwardedTo": awarded,
            "needsReview": False,
            "rawText": text,
            "playerId": None,
            "teamId": teamId,
            "matchId": matchId,
        }

    # find best matching event phrase using word boundaries to avoid partial matches
    matched = None

    for phrase in sorted(EVENT_MAP.keys(), key=len, reverse=True):
        if phrase in ("point us", "point them"):
            continue
        if re.search(rf"\b{re.escape(phrase)}\b", cleaned):
            matched = phrase
            break

    if player is None or matched is None:
        return {
            "setNumber": setNumber,
            "playerNumber": player,
            "event": "UNKNOWN",
            "pointAwardedTo": None,
            "needsReview": True,
            "rawText": text,
            "playerId": None,
            "teamId": teamId,
            "matchId": matchId,
        }
    
    event, awarded = EVENT_MAP[matched]
    return {
        "setNumber": setNumber,
        "playerNumber": player,
        "event": event,
        "pointAwardedTo": awarded,
        "needsReview": False,
        "rawText": text,
        "playerId": None,
        "teamId": teamId,
        "matchId": matchId,
    }


@app.get("/")
def root():
    return {"Hello": "World"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/parse-text", response_model=ParsedEvent)
def parse_text(request: ParseTextRequest):
    return parse_command(
        request.text,
        request.setNumber,
        request.teamId,
        request.matchId,
    )

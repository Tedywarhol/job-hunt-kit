#!/usr/bin/env python3
"""Lecture Gmail robuste pour les gros volumes : quota respecté, reprise possible.

Constat (2026-10-02 puis 2026-10-06) : au-delà de quelques centaines de messages, l'API répond 403
« Units per minute per user ». Chaque appel passe donc par `execute()` (attente croissante puis
nouvel essai), et chaque message lu est gardé dans un cache disque : une reprise ne relit rien.
"""
import base64
import html
import json
import os
import re
import time
from datetime import date
from typing import Any, Dict, List

from googleapiclient.errors import HttpError

PAUSE_S: float = 0.12
RETRYABLE = {403, 429, 500, 503}
MAX_TRIES: int = 7
SAVE_EVERY: int = 50


def execute(request: Any) -> Dict[str, Any]:
    """Exécute une requête Gmail ; sur quota ou panne passagère, attend 2, 4, 8... secondes et réessaie."""
    for attempt in range(MAX_TRIES):
        try:
            result: Dict[str, Any] = request.execute()
            time.sleep(PAUSE_S)
            return result
        except HttpError as e:
            if e.resp.status not in RETRYABLE or attempt == MAX_TRIES - 1:
                raise
            time.sleep(2 ** (attempt + 1))
    raise RuntimeError("execute: nombre d'essais épuisé")  # inatteignable, pour le typage


class GmailReader:
    """Accès Gmail avec cache disque des en-têtes et des corps déjà lus."""

    def __init__(self, service: Any, cache_path: str) -> None:
        self.service = service
        self.cache_path = cache_path
        self.cache: Dict[str, Dict[str, Any]] = {"headers": {}, "bodies": {}, "threads": {}}
        if os.path.exists(cache_path):
            with open(cache_path, encoding="utf-8") as f:
                self.cache.update(json.load(f))
        self.unsaved = 0

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, ensure_ascii=False)
        self.unsaved = 0

    def _stored(self, kind: str, key: str, value: Any) -> Any:
        self.cache[kind][key] = value
        self.unsaved += 1
        if self.unsaved >= SAVE_EVERY:
            self.save()
        return value

    def ids(self, query: str) -> List[Dict[str, str]]:
        found, token = [], None
        while True:
            page = execute(self.service.users().messages().list(userId="me", q=query, maxResults=500, pageToken=token))
            found += page.get("messages", [])
            token = page.get("nextPageToken")
            if not token:
                return found

    def headers(self, msg_id: str) -> Dict[str, Any]:
        if msg_id in self.cache["headers"]:
            return self.cache["headers"][msg_id]
        msg = execute(self.service.users().messages().get(
            userId="me", id=msg_id, format="metadata", metadataHeaders=["From", "To", "Cc", "Subject"]))
        head = header_dict(msg)
        return self._stored("headers", msg_id, head)

    def thread(self, thread_id: str) -> List[Dict[str, Any]]:
        if thread_id in self.cache["threads"]:
            return self.cache["threads"][thread_id]
        data = execute(self.service.users().threads().get(
            userId="me", id=thread_id, format="metadata", metadataHeaders=["From", "Subject"]))
        return self._stored("threads", thread_id, [header_dict(m) for m in data["messages"]])

    def body(self, msg_id: str) -> str:
        if msg_id in self.cache["bodies"]:
            return self.cache["bodies"][msg_id]
        msg = execute(self.service.users().messages().get(userId="me", id=msg_id, format="full"))
        return self._stored("bodies", msg_id, text_part(msg["payload"])[:6000])


def header_dict(msg: Dict[str, Any]) -> Dict[str, Any]:
    head = {h["name"].lower(): h["value"] for h in msg["payload"]["headers"]}
    head["date"] = date.fromtimestamp(int(msg["internalDate"]) / 1000).isoformat()
    head["thread"] = msg["threadId"]
    head["id"] = msg["id"]
    return head


def text_part(part: Dict[str, Any]) -> str:
    data = part.get("body", {}).get("data")
    if part.get("mimeType") == "text/plain" and data:
        return base64.urlsafe_b64decode(data).decode("utf-8", "replace")
    for sub in part.get("parts", []) or []:
        found = text_part(sub)
        if found:
            return found
    if part.get("mimeType") == "text/html" and data:
        raw = base64.urlsafe_b64decode(data).decode("utf-8", "replace")
        raw = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>", "\n", raw)
        return html.unescape(re.sub(r"<[^>]+>", " ", raw))
    return ""

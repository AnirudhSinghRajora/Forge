"""Exercises the Gemini wrappers against a local stub of the documented REST shapes.

This proves our requests pass the SDK's own validation and that we read the documented response
fields. It does not prove that Gemini accepts the requests. `python -m app.agent.llm --selftest` is
the real test and needs a key.
"""
import base64
import http.server
import json
import threading

import httpx
import pytest

from app import config
from app.agent import llm

STATE = {"requests": [], "responses": {}}
# Captured at import, before the autouse fixture in conftest blocks real transports.
_ORIGINAL = httpx.HTTPTransport.handle_request


class Stub(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["content-length"])) or b"{}")
        STATE["requests"].append((self.path, body))
        key = "interactions" if "interactions" in self.path else "other"
        payload = STATE["responses"].get(key, {})
        data = json.dumps(payload).encode()
        status = 200 if payload else 500
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


@pytest.fixture
def gemini_stub(monkeypatch):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Stub)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    monkeypatch.setenv("GEMINI_API_KEY", "stub-key")
    monkeypatch.setenv("GOOGLE_GEMINI_BASE_URL", url)
    config.get_settings.cache_clear()
    monkeypatch.setattr(llm, "_client", None)
    STATE["requests"].clear()
    STATE["responses"].clear()

    def only_stub(self, request):
        if request.url.host == "127.0.0.1":
            return _ORIGINAL(self, request)
        raise httpx.ConnectError("blocked")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", only_stub)
    yield STATE
    server.shutdown()


def interaction(steps=None, **extra):
    return {"id": "i1", "status": "completed", "steps": steps or [], **extra}


def output_text(text, annotations=None):
    block = {"type": "text", "text": text}
    if annotations:
        block["annotations"] = annotations
    return {"type": "model_output", "content": [block]}


def test_parse_text_through_interactions(gemini_stub):
    gemini_stub["responses"]["interactions"] = interaction(steps=[output_text(json.dumps({
        "transcript": "ओले", "crop": "cotton", "event_type": "hail", "event_date": "2026-10-20",
        "event_time": None, "confidence": 0.9}))])
    report = llm.parse_text("ओले गिरे", "hi")
    assert report and report.crop == "cotton" and report.llm_used
    path, body = gemini_stub["requests"][0]
    assert "interactions" in path and body["response_format"]["mime_type"] == "application/json"
    assert body["store"] is False


def test_parse_rejects_future_dates_and_bad_types(gemini_stub):
    gemini_stub["responses"]["interactions"] = interaction(steps=[output_text(json.dumps({
        "transcript": "x", "event_type": "meteor", "event_date": "2099-01-01", "confidence": 3}))])
    report = llm.parse_text("x")
    assert report.event_type == "unknown" and report.event_date is None and report.confidence == 1.0


def test_plan_reads_the_function_call_step(gemini_stub):
    gemini_stub["responses"]["interactions"] = interaction(steps=[{
        "type": "function_call", "id": "c1", "name": "sar_first",
        "arguments": {"rationale": "cloud"}}])
    options = [{"name": "sar_first", "description": "radar",
                "parameters": {"type": "object", "properties": {"rationale": {"type": "string"}}}}]
    choice = llm.plan("context", options)
    assert choice and choice.name == "sar_first" and choice.rationale == "cloud"
    body = gemini_stub["requests"][0][1]
    assert body["tools"][0]["name"] == "sar_first" and body["tools"][0]["type"] == "function"


def test_search_returns_only_cited_urls(gemini_stub):
    text = "Hail hit the district."
    gemini_stub["responses"]["interactions"] = interaction(steps=[output_text(text, [
        {"type": "url_citation", "url": "https://news.example/a", "title": "example", "start_index": 0,
         "end_index": 4}])])
    sources = llm.grounded_sources("q")
    assert sources == [{"url": "https://news.example/a", "title": "example"}]


def test_tts_reads_wav(gemini_stub):
    wav = b"RIFF" + b"\x00" * 40
    gemini_stub["responses"]["interactions"] = interaction(steps=[{
        "type": "model_output",
        "content": [{"type": "audio", "data": base64.b64encode(wav).decode(), "mime_type": "audio/wav"}]}])
    assert llm.tts("नमस्ते", "hi") == wav


def test_server_error_falls_through_to_none(gemini_stub):
    assert llm.narrate({"x": 1}, "hi") is None
    paths = [p for p, _ in gemini_stub["requests"]]
    assert any("interactions" in p for p in paths) and any("generateContent" in p for p in paths)


def test_images_pass_the_sdks_own_validation(gemini_stub):
    gemini_stub["responses"]["interactions"] = interaction(steps=[output_text(json.dumps({
        "description_hi": "भूरा", "description_en": "Browner", "description_te": "గోధుమ",
        "visible_change": "clear", "consistent": "yes"}))])
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
    opinion = llm.read_images([("true colour, before", png)], {"ndvi_before": 0.7})
    assert opinion and opinion.consistent == "yes"
    path, body = gemini_stub["requests"][0]
    assert "interactions" in path and body["store"] is False
    assert body["response_format"]["mime_type"] == "application/json"
    parts = body["input"][0]["content"]  # the SDK wraps a list of parts as one user turn
    image = next(p for p in parts if p.get("type") == "image")
    assert image["mime_type"] == "image/png" and base64.b64decode(image["data"]) == png


def test_the_witness_answer_passes_the_sdks_own_validation(gemini_stub):
    gemini_stub["responses"]["interactions"] = interaction(steps=[output_text(json.dumps({
        "covered": True, "answer": "ok", "cited_fields": ["verdict.level"], "cited_clause_ids": []}))])
    answer = llm.answer_from_record("why?", {"verdict.level": "weak"}, [], "en")
    assert answer and answer.covered and answer.cited_fields == ["verdict.level"]
    schema = gemini_stub["requests"][0][1]["response_format"]["schema"]
    assert schema["properties"]["cited_fields"]["type"] == "array"


def test_the_statement_check_passes_the_sdks_own_validation(gemini_stub):
    gemini_stub["responses"]["interactions"] = interaction(steps=[output_text(json.dumps({
        "found": True, "about": "date", "question_hi": "क्या?", "question_en": "Which day?", "question_te": "ఏ రోజు?"}))])
    check = llm.find_contradiction({"transcript": "x"}, {"event.date": "2026-03-09"})
    assert check and check.about == "date"
    schema = gemini_stub["requests"][0][1]["response_format"]["schema"]
    assert schema["properties"]["about"]["enum"] == ["date", "event", "crop_stage", "none"]
    assert "$defs" not in schema  # the documented schema subset does not list $defs, so none is sent

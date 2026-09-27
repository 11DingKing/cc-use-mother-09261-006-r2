"""JSON API 适配器。"""
from .verification import CREATED, REPLAYED, CONFLICT, LABELS

_STATUS = {CREATED: 201, REPLAYED: 200, CONFLICT: 409}


def _submission_body(sub):
    rec = sub.record
    body = {"outcome": sub.outcome, "outcome_label": LABELS[sub.outcome], "resource_id": rec.resource_id,
            "state": rec.state, "result": rec.result, "fingerprint": rec.fingerprint,
            "version": rec.version, "created_at": rec.created_at}
    if sub.outcome == CONFLICT:
        body.update({"error": "content_mismatch", "expected_fingerprint": rec.fingerprint,
                     "submitted_fingerprint": sub.submitted_fingerprint,
                     "message": "同一编号报送内容不一致，已阻止覆盖，保留首次核验记录"})
    return body


def _attempt_body(a):
    return dict(a, label=LABELS[a["classification"]])


def _submit(verifications, body):
    missing = [k for k in ("resource_id", "actor", "content") if k not in body]
    if missing:
        return 400, {"error": "bad_request", "missing": missing}
    sub = verifications.submit(body["resource_id"], body["actor"], body["content"])
    return _STATUS[sub.outcome], _submission_body(sub)


def dispatch(flow, method, path, body=None, verifications=None):
    body = body or {}
    parts = path.strip("/").split("/")
    if method == "POST" and path == "/cases":
        return 201, flow.create(body["id"], body["actor"], body.get("idempotency_key")).__dict__
    if method == "POST" and path.endswith("/move"):
        return 200, flow.move(parts[1], body["state"], body["actor"]).__dict__
    if method == "GET" and path == "/cases":
        return 200, flow.snapshot()
    if verifications is not None:
        if method == "POST" and path == "/verifications":
            return _submit(verifications, body)
        if method == "GET" and path == "/verifications":
            return 200, verifications.list()
        if method == "GET" and len(parts) == 2 and parts[0] == "verifications":
            rec = verifications.get(parts[1])
            return (200, rec) if rec else (404, {"error": "not_found"})
        if method == "GET" and len(parts) == 3 and parts[0] == "verifications" and parts[2] == "attempts":
            if verifications.get(parts[1]) is None:
                return 404, {"error": "not_found"}
            return 200, [_attempt_body(a) for a in verifications.attempts(parts[1])]
        if method == "GET" and path == "/attempts":
            return 200, [_attempt_body(a) for a in verifications.attempts()]
    return 404, {"error": "not_found"}

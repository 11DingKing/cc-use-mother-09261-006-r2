"""数字教材资源提交核验：幂等识别、冲突阻止与审计留痕。"""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib, json

CREATED, REPLAYED, CONFLICT = "created", "replayed", "conflict"
LABELS = {CREATED: "首次提交", REPLAYED: "幂等重试", CONFLICT: "冲突尝试"}
SUPPORTED_FORMATS = {"video", "audio", "document", "image", "interactive"}


def now():
    return datetime.now(timezone.utc).isoformat()


def fingerprint(content):
    """对报送内容取规范化 JSON 的 SHA-256，作为可审计的校验依据。"""
    canonical = json.dumps(content, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def run_checks(content):
    """确定性核验规则，同一内容必然得到同一结果。"""
    checks = [
        {"name": "content_is_object", "ok": isinstance(content, dict)},
        {"name": "title_present", "ok": isinstance(content, dict) and isinstance(content.get("title"), str) and bool(content["title"].strip())},
        {"name": "format_supported", "ok": isinstance(content, dict) and content.get("format") in SUPPORTED_FORMATS},
    ]
    return {"passed": all(c["ok"] for c in checks), "checks": checks}


@dataclass(frozen=True)
class Record:
    """一次核验的存档：编号、报送方、内容指纹、结论与结果，建账后不可改。"""
    resource_id: str
    actor: str
    fingerprint: str
    state: str  # verified | rejected
    result: dict
    created_at: str
    version: int = 1


@dataclass(frozen=True)
class Submission:
    """一次提交的结局：outcome 为 created/replayed/conflict，record 始终是存档中的原记录。"""
    outcome: str
    record: Record
    submitted_fingerprint: str


class VerificationService:
    """同一资源编号只核验一次：重试返回原结果，内容不一致拒绝覆盖，逐次留痕。"""

    def __init__(self, store):
        self.store = store

    def submit(self, resource_id, actor, content):
        fp = fingerprint(content)
        existing = self.store.get_record(resource_id)
        if existing is None:
            result = run_checks(content)
            record = Record(resource_id, actor, fp, "verified" if result["passed"] else "rejected", result, now())
            if self.store.put_record(asdict(record)):
                self.store.log_attempt(resource_id, actor, fp, CREATED, {"message": "首次提交，已建立核验记录"})
                return Submission(CREATED, record, fp)
            existing = self.store.get_record(resource_id)  # 并发下他人已抢先建档，按已有记录判定
        existing = Record(**existing)
        if existing.fingerprint == fp:
            self.store.log_attempt(resource_id, actor, fp, REPLAYED, {"message": "内容指纹一致，返回原核验结果"})
            return Submission(REPLAYED, existing, fp)
        self.store.log_attempt(resource_id, actor, fp, CONFLICT, {"expected_fingerprint": existing.fingerprint, "message": "内容指纹不一致，已阻止覆盖"})
        return Submission(CONFLICT, existing, fp)

    def get(self, resource_id):
        return self.store.get_record(resource_id)

    def list(self):
        return self.store.list_records()

    def attempts(self, resource_id=None):
        return self.store.list_attempts(resource_id)

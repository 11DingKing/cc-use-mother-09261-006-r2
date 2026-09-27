import os
import tempfile
import unittest

from service_09261_006.api import dispatch
from service_09261_006.store import SQLiteStore
from service_09261_006.verification import CONFLICT, CREATED, REPLAYED, VerificationService
from service_09261_006.workflow import Workflow

CONTENT = {"title": "三年级语文·上册", "format": "document", "pages": 120}
OTHER = {"title": "被掉包的内容", "format": "video"}


class TestFlow(unittest.TestCase):
    def test_flow(self):
        f = Workflow()
        self.assertEqual(f.create("c1", "a", "k").state, "draft")
        self.assertEqual(f.create("c1", "a", "k").version, 1)
        self.assertEqual(f.move("c1", "reviewing", "b").state, "reviewing")


class TestVerification(unittest.TestCase):
    def setUp(self):
        self.svc = VerificationService(SQLiteStore())

    def test_created_then_replayed_returns_original(self):
        first = self.svc.submit("R-1001", "supplier-a", CONTENT)
        self.assertEqual(first.outcome, CREATED)
        self.assertEqual(first.record.state, "verified")
        again = self.svc.submit("R-1001", "supplier-a", dict(CONTENT))
        self.assertEqual(again.outcome, REPLAYED)
        self.assertEqual(again.record.result, first.record.result)
        self.assertEqual(again.record.created_at, first.record.created_at)
        self.assertEqual(len(self.svc.list()), 1)

    def test_conflict_does_not_overwrite(self):
        first = self.svc.submit("R-1002", "supplier-a", CONTENT)
        other = self.svc.submit("R-1002", "supplier-b", OTHER)
        self.assertEqual(other.outcome, CONFLICT)
        kept = self.svc.get("R-1002")
        self.assertEqual(kept["fingerprint"], first.record.fingerprint)
        self.assertEqual(kept["actor"], "supplier-a")
        self.assertEqual(kept["result"], first.record.result)

    def test_audit_trail_distinguishes_outcomes(self):
        self.svc.submit("R-1003", "supplier-a", CONTENT)
        self.svc.submit("R-1003", "supplier-a", CONTENT)
        self.svc.submit("R-1003", "supplier-b", OTHER)
        attempts = self.svc.attempts("R-1003")
        self.assertEqual([a["classification"] for a in attempts], [CREATED, REPLAYED, CONFLICT])
        self.assertIn("expected_fingerprint", attempts[2]["detail"])

    def test_failed_verification_is_recorded_and_replayed(self):
        bad = self.svc.submit("R-1004", "supplier-a", {"format": "document"})
        self.assertEqual(bad.record.state, "rejected")
        retry = self.svc.submit("R-1004", "supplier-a", {"format": "document"})
        self.assertEqual(retry.outcome, REPLAYED)
        self.assertEqual(retry.record.state, "rejected")

    def test_records_survive_restart(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "audit.db")
            VerificationService(SQLiteStore(path)).submit("R-1005", "supplier-a", CONTENT)
            svc = VerificationService(SQLiteStore(path))
            self.assertEqual(svc.submit("R-1005", "supplier-a", CONTENT).outcome, REPLAYED)
            self.assertEqual(len(svc.attempts("R-1005")), 2)


class TestApi(unittest.TestCase):
    def setUp(self):
        self.flow = Workflow()
        self.vc = VerificationService(SQLiteStore())

    def post(self, body):
        return dispatch(self.flow, "POST", "/verifications", body, verifications=self.vc)

    def test_submit_created_replayed_conflict_status(self):
        s1, b1 = self.post({"resource_id": "R-1", "actor": "a", "content": CONTENT})
        self.assertEqual((s1, b1["outcome"]), (201, "created"))
        s2, b2 = self.post({"resource_id": "R-1", "actor": "a", "content": dict(CONTENT)})
        self.assertEqual((s2, b2["outcome"]), (200, "replayed"))
        self.assertEqual(b2["result"], b1["result"])
        s3, b3 = self.post({"resource_id": "R-1", "actor": "b", "content": OTHER})
        self.assertEqual((s3, b3["outcome"], b3["error"]), (409, "conflict", "content_mismatch"))
        self.assertEqual(b3["expected_fingerprint"], b1["fingerprint"])
        self.assertNotEqual(b3["submitted_fingerprint"], b1["fingerprint"])

    def test_missing_fields_400(self):
        status, body = self.post({"resource_id": "R-2"})
        self.assertEqual(status, 400)
        self.assertEqual(body["missing"], ["actor", "content"])

    def test_review_endpoints_distinguish_attempts(self):
        self.post({"resource_id": "R-3", "actor": "a", "content": CONTENT})
        self.post({"resource_id": "R-3", "actor": "a", "content": CONTENT})
        self.post({"resource_id": "R-3", "actor": "b", "content": OTHER})
        status, attempts = dispatch(self.flow, "GET", "/verifications/R-3/attempts", verifications=self.vc)
        self.assertEqual(status, 200)
        self.assertEqual([a["label"] for a in attempts], ["首次提交", "幂等重试", "冲突尝试"])
        status, rec = dispatch(self.flow, "GET", "/verifications/R-3", verifications=self.vc)
        self.assertEqual((status, rec["state"]), (200, "verified"))
        status, _ = dispatch(self.flow, "GET", "/verifications/nope", verifications=self.vc)
        self.assertEqual(status, 404)
        status, listing = dispatch(self.flow, "GET", "/verifications", verifications=self.vc)
        self.assertEqual([r["resource_id"] for r in listing], ["R-3"])

    def test_cases_routes_still_work(self):
        status, _ = dispatch(self.flow, "POST", "/cases", {"id": "c1", "actor": "a"}, verifications=self.vc)
        self.assertEqual(status, 201)


if __name__ == "__main__":
    unittest.main()

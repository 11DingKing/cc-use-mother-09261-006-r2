import unittest
from service_09261_006.workflow import Workflow,fingerprint
from service_09261_006.store import SQLiteStore
from service_09261_006.api import dispatch

A={"isbn":"978-7-04-000001-0","title":"小学数学一年级上册","files":["a1.pdf","a2.pdf"]}
B={"isbn":"978-7-04-000001-0","title":"小学数学一年级上册（修订版）","files":["b1.pdf"]}

class TestSubmit(unittest.TestCase):
 def test_first_submit_created(self):
  r=Workflow().submit("R1","supplier-a",A)
  self.assertEqual(r.outcome,"created"); self.assertEqual(r.case.state,"draft"); self.assertEqual(r.digest,r.stored_digest)
 def test_same_content_is_idempotent_retry(self):
  f=Workflow(); first=f.submit("R1","supplier-a",A)
  f.move("R1","reviewing","ops")
  retry=f.submit("R1","supplier-a",A)
  self.assertEqual(retry.outcome,"replayed")
  self.assertEqual(retry.case,first.case)
  self.assertEqual(retry.digest,retry.stored_digest)
  self.assertEqual(f.rows["R1"].state,"reviewing")
  self.assertEqual(len(f.attempts),2)
 def test_duplicate_from_other_supplier_replayed(self):
  f=Workflow(); f.submit("R1","supplier-a",A)
  shuffled=dict(reversed(list(A.items())))
  self.assertEqual(f.submit("R1","supplier-b",shuffled).outcome,"replayed")
 def test_changed_content_is_conflict_and_blocked(self):
  f=Workflow(); f.submit("R1","supplier-a",A)
  r=f.submit("R1","supplier-b",B)
  self.assertEqual(r.outcome,"conflict"); self.assertNotEqual(r.digest,r.stored_digest)
  self.assertEqual(r.stored_digest,fingerprint(A)); self.assertEqual(r.digest,fingerprint(B))
  self.assertEqual(f.digests["R1"],fingerprint(A))
  self.assertEqual(f.rows["R1"].state,"draft")
 def test_fingerprint_ignores_key_order(self):
  self.assertEqual(fingerprint({"x":1,"y":[1,2]}),fingerprint({"y":[1,2],"x":1}))
 def test_audit_trail_distinguishes_outcomes(self):
  f=Workflow(); f.submit("R1","a",A); f.submit("R1","a",A); f.submit("R1","b",B)
  self.assertEqual([a.outcome for a in f.attempts],["created","replayed","conflict"])
  self.assertEqual(f.attempts[1].ref,f.attempts[0].seq); self.assertEqual(f.attempts[2].ref,f.attempts[0].seq)
 def test_move_and_legacy_create(self):
  f=Workflow(); self.assertEqual(f.create("c1","a","k").state,"draft"); self.assertEqual(f.create("c1","a","k").version,1)
  self.assertEqual(f.move("c1","reviewing","b").state,"reviewing")
  with self.assertRaises(ValueError): f.move("c1","archived","b")

class TestApi(unittest.TestCase):
 def setUp(self): self.f=Workflow()
 def test_submit_status_codes(self):
  s,b=dispatch(self.f,"POST","/cases",{"id":"R1","actor":"a","content":A}); self.assertEqual((s,b["outcome"]),(201,"created"))
  s,b=dispatch(self.f,"POST","/cases",{"id":"R1","actor":"a","content":A}); self.assertEqual((s,b["outcome"]),(200,"replayed"))
  s,b=dispatch(self.f,"POST","/cases",{"id":"R1","actor":"b","content":B})
  self.assertEqual((s,b["outcome"]),(409,"conflict")); self.assertIn("message",b)
 def test_review_endpoints(self):
  dispatch(self.f,"POST","/cases",{"id":"R1","actor":"a","content":A})
  dispatch(self.f,"POST","/cases",{"id":"R1","actor":"a","content":A})
  dispatch(self.f,"POST","/cases",{"id":"R1","actor":"b","content":B})
  s,cases=dispatch(self.f,"GET","/cases"); self.assertEqual((s,len(cases)),(200,1)); self.assertEqual(cases[0]["attempts"],3)
  s,d=dispatch(self.f,"GET","/cases/R1"); self.assertEqual(s,200)
  self.assertEqual([a["outcome"] for a in d["attempts"]],["created","replayed","conflict"])
  s,atts=dispatch(self.f,"GET","/cases/R1/attempts"); self.assertEqual(len(atts),3)
  s,allatts=dispatch(self.f,"GET","/attempts"); self.assertEqual(len(allatts),3)
  s,_=dispatch(self.f,"GET","/cases/R9"); self.assertEqual(s,404)
 def test_move_endpoint(self):
  dispatch(self.f,"POST","/cases",{"id":"R1","actor":"a","content":A})
  s,b=dispatch(self.f,"POST","/cases/R1/move",{"state":"reviewing","actor":"ops"}); self.assertEqual((s,b["state"]),(200,"reviewing"))
  s,_=dispatch(self.f,"POST","/cases/R1/move",{"state":"draft","actor":"ops"}); self.assertEqual(s,400)
  s,_=dispatch(self.f,"POST","/cases/R9/move",{"state":"reviewing","actor":"ops"}); self.assertEqual(s,404)

class TestStore(unittest.TestCase):
 def test_attempts_persisted_for_audit(self):
  store=SQLiteStore(); f=Workflow(store=store)
  f.submit("R1","a",A); f.submit("R1","a",A); f.submit("R1","b",B)
  self.assertEqual([a["outcome"] for a in store.attempts()],["created","replayed","conflict"])
  self.assertEqual(len(store.attempts("R1")),3); self.assertEqual(store.attempts("R9"),[])

if __name__=="__main__": unittest.main()

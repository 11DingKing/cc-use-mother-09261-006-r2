"""版本化业务工作流。"""
import hashlib,json
from dataclasses import dataclass,asdict
from datetime import datetime,timezone

def _now(): return datetime.now(timezone.utc).isoformat()

def fingerprint(content):
 """对报送内容生成规范化指纹，作为核验与审计的比对依据。"""
 return hashlib.sha256(json.dumps(content,sort_keys=True,ensure_ascii=False).encode("utf-8")).hexdigest()

@dataclass(frozen=True)
class Case:
 id:str; actor:str; state:str; version:int=1
 def move(self,state,actor):
  allowed={"draft":{"reviewing","cancelled"},"reviewing":{"approved","rejected"},"rejected":{"draft"},"approved":{"archived"}}
  if state not in allowed.get(self.state,set()): raise ValueError("invalid transition")
  return Case(self.id,actor,state,self.version+1)

@dataclass(frozen=True)
class Attempt:
 """一次报送尝试的审计记录；outcome 取值 created/replayed/conflict，ref 指向该资源首次提交的序号。"""
 seq:int; resource_id:str; actor:str; digest:str; outcome:str; at:str; ref:int=0

@dataclass(frozen=True)
class Receipt:
 """报送回执；case 为在档的原始核验结果，stored_digest 为在档内容指纹。"""
 outcome:str; case:Case; digest:str; stored_digest:str; attempt_seq:int

class Workflow:
 """资源核验：同一编号内容一致视为同一次核验并返回原结果，内容不一致拒绝覆盖并留痕。"""
 def __init__(self,store=None):
  self.rows={}; self.digests={}; self.filed={}; self.origin={}; self.keys={}; self.attempts=[]; self.store=store
 def _record(self,id,actor,digest,outcome,ref=0):
  a=Attempt(len(self.attempts)+1,id,actor,digest,outcome,_now(),ref); self.attempts.append(a)
  if self.store: self.store.save_attempt(asdict(a))
  return a
 def submit(self,id,actor,content=None,key=None):
  digest=fingerprint(content)
  if id in self.rows:
   kept=self.digests[id]; ref=self.origin[id]
   outcome="replayed" if digest==kept else "conflict"
   a=self._record(id,actor,digest,outcome,ref)
   return Receipt(outcome,self.filed[id],digest,kept,a.seq)
  row=Case(id,actor,"draft"); self.rows[id]=row; self.digests[id]=digest; self.filed[id]=row
  if key: self.keys[key]=id
  a=self._record(id,actor,digest,"created"); self.origin[id]=a.seq
  return Receipt("created",row,digest,digest,a.seq)
 def create(self,id,actor,key=None): return self.submit(id,actor,None,key).case
 def move(self,id,state,actor): self.rows[id]=self.rows[id].move(state,actor); return self.rows[id]
 def snapshot(self):
  return [dict(asdict(self.rows[k]),digest=self.digests[k],attempts=len(self.history(k))) for k in sorted(self.rows)]
 def history(self,id): return [asdict(a) for a in self.attempts if a.resource_id==id]
 def journal(self): return [asdict(a) for a in self.attempts]
 def detail(self,id):
  if id not in self.rows: return None
  return {"case":asdict(self.rows[id]),"digest":self.digests[id],"attempts":self.history(id)}

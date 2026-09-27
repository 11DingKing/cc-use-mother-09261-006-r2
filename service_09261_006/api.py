"""JSON API 适配器。"""
from dataclasses import asdict
STATUS={"created":201,"replayed":200,"conflict":409}
def dispatch(flow,method,path,body=None):
 body=body or {}; parts=path.strip("/").split("/")
 if method=="POST" and path=="/cases":
  r=flow.submit(body["id"],body["actor"],body.get("content"),body.get("idempotency_key"))
  out=asdict(r)
  if r.outcome=="conflict": out["message"]="报送内容与在档核验不一致，已阻止覆盖"
  return STATUS[r.outcome],out
 if method=="POST" and len(parts)==3 and parts[0]=="cases" and parts[2]=="move":
  if parts[1] not in flow.rows: return 404,{"error":"not_found"}
  try: return 200,asdict(flow.move(parts[1],body["state"],body["actor"]))
  except ValueError: return 400,{"error":"invalid_transition"}
 if method=="GET" and path=="/cases": return 200,flow.snapshot()
 if method=="GET" and len(parts)==2 and parts[0]=="cases":
  d=flow.detail(parts[1]); return (200,d) if d else (404,{"error":"not_found"})
 if method=="GET" and len(parts)==3 and parts[0]=="cases" and parts[2]=="attempts": return 200,flow.history(parts[1])
 if method=="GET" and path=="/attempts": return 200,flow.journal()
 return 404,{"error":"not_found"}

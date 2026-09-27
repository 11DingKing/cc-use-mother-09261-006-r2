"""SQLite 状态仓储。"""
import sqlite3,json
class SQLiteStore:
 def __init__(self,path=":memory:"):
  self.db=sqlite3.connect(path)
  self.db.execute("CREATE TABLE IF NOT EXISTS snapshots(id INTEGER PRIMARY KEY AUTOINCREMENT,body TEXT NOT NULL)")
  self.db.execute("CREATE TABLE IF NOT EXISTS attempts(seq INTEGER PRIMARY KEY,body TEXT NOT NULL)")
  self.db.commit()
 def save(self,value): self.db.execute("INSERT INTO snapshots(body) VALUES(?)",(json.dumps(value,ensure_ascii=False),)); self.db.commit()
 def latest(self):
  row=self.db.execute("SELECT body FROM snapshots ORDER BY id DESC LIMIT 1").fetchone(); return json.loads(row[0]) if row else []
 def save_attempt(self,attempt):
  self.db.execute("INSERT INTO attempts(seq,body) VALUES(?,?)",(attempt["seq"],json.dumps(attempt,ensure_ascii=False))); self.db.commit()
 def attempts(self,resource_id=None):
  rows=[json.loads(r[0]) for r in self.db.execute("SELECT body FROM attempts ORDER BY seq")]
  return [a for a in rows if a["resource_id"]==resource_id] if resource_id else rows

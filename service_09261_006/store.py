"""SQLite 状态仓储：核验记录只增不改，提交尝试逐条留痕。"""
import sqlite3, json
from datetime import datetime, timezone


class SQLiteStore:
    def __init__(self, path=":memory:"):
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS records(resource_id TEXT PRIMARY KEY, body TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS attempts(id INTEGER PRIMARY KEY AUTOINCREMENT, resource_id TEXT NOT NULL, classification TEXT NOT NULL, actor TEXT NOT NULL, fingerprint TEXT NOT NULL, detail TEXT NOT NULL, at TEXT NOT NULL)")
        self.db.commit()

    def put_record(self, body):
        """建档成功返回 True；编号已存在返回 False，绝不覆盖。"""
        try:
            self.db.execute("INSERT INTO records(resource_id, body) VALUES(?, ?)", (body["resource_id"], json.dumps(body, ensure_ascii=False)))
            self.db.commit()
            return True
        except sqlite3.IntegrityError:
            self.db.rollback()
            return False

    def get_record(self, resource_id):
        row = self.db.execute("SELECT body FROM records WHERE resource_id=?", (resource_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def list_records(self):
        rows = self.db.execute("SELECT body FROM records ORDER BY resource_id").fetchall()
        return [json.loads(r[0]) for r in rows]

    def log_attempt(self, resource_id, actor, fingerprint, classification, detail):
        at = datetime.now(timezone.utc).isoformat()
        self.db.execute("INSERT INTO attempts(resource_id, classification, actor, fingerprint, detail, at) VALUES(?, ?, ?, ?, ?, ?)", (resource_id, classification, actor, fingerprint, json.dumps(detail, ensure_ascii=False), at))
        self.db.commit()

    def list_attempts(self, resource_id=None):
        sql = "SELECT id, resource_id, classification, actor, fingerprint, detail, at FROM attempts"
        args = ()
        if resource_id is not None:
            sql += " WHERE resource_id=?"
            args = (resource_id,)
        rows = self.db.execute(sql + " ORDER BY id", args).fetchall()
        return [{"seq": r[0], "resource_id": r[1], "classification": r[2], "actor": r[3], "fingerprint": r[4], "detail": json.loads(r[5]), "at": r[6]} for r in rows]

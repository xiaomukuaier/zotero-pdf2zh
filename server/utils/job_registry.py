import hashlib
import json
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path


def request_fingerprint(content, configuration, operation):
    payload = json.dumps(configuration, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256()
    for value in (content, payload.encode(), operation.encode()):
        digest.update(len(value).to_bytes(8, "big"))
        digest.update(value)
    return digest.hexdigest()


def file_digest(path):
    with open(path, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class JobRegistry:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as connection, connection:
            connection.execute("CREATE TABLE IF NOT EXISTS jobs (fingerprint TEXT PRIMARY KEY, task_id TEXT UNIQUE NOT NULL, status TEXT NOT NULL, result TEXT, files TEXT)")

    def connect(self):
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def recover_interrupted(self):
        # 服务启动时调用；同一数据目录只运行一个服务实例。
        with closing(self.connect()) as connection, connection:
            connection.execute("UPDATE jobs SET status='failed' WHERE status='running'")

    def claim(self, fingerprint):
        with closing(self.connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM jobs WHERE fingerprint=?", (fingerprint,)).fetchone()
            if row and row["status"] == "running":
                return False, {"taskId": row["task_id"], "status": "running"}
            if row and row["status"] == "success":
                files = json.loads(row["files"])
                if files and all(Path(path).is_file() and file_digest(path) == digest for path, digest in files.items()):
                    return False, {"taskId": row["task_id"], "status": "success", "result": json.loads(row["result"])}
            task_id = str(uuid.uuid4())
            connection.execute("INSERT INTO jobs VALUES (?, ?, 'running', NULL, NULL) ON CONFLICT(fingerprint) DO UPDATE SET task_id=excluded.task_id, status='running', result=NULL, files=NULL", (fingerprint, task_id))
            return True, {"taskId": task_id, "status": "running"}

    def complete(self, task_id, result):
        paths = result.get("filePaths", [])
        if not paths or any(not Path(path).is_file() or Path(path).stat().st_size == 0 for path in paths):
            raise ValueError("Completed job has no valid output files")
        files = {path: file_digest(path) for path in paths}
        with closing(self.connect()) as connection, connection:
            connection.execute("UPDATE jobs SET status='success', result=?, files=? WHERE task_id=?", (json.dumps(result), json.dumps(files), task_id))

    def fail(self, task_id):
        with closing(self.connect()) as connection, connection:
            connection.execute("UPDATE jobs SET status='failed' WHERE task_id=? AND status='running'", (task_id,))

    def get(self, task_id):
        with closing(self.connect()) as connection:
            row = connection.execute("SELECT status, result FROM jobs WHERE task_id=?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(task_id)
        return {"status": row["status"], "result": json.loads(row["result"]) if row["result"] else None}

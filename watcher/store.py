"""
Flat-file state. data/posts.json is committed back to the repo by the
workflow, which is what gives us dedupe across runs and a history to build the
weekly digest from - no database, nothing to pay for.
"""

import json
import os
import tempfile
from datetime import datetime, timezone

DEFAULT_STATE = {
    "version": 1,
    "posts": {},          # id -> post record
    "alerted": {},        # id -> iso timestamp we emailed about it
    "runs": [],           # short audit trail of the last runs
}


class Store(object):
    def __init__(self, path):
        self.path = path
        self.state = self._load()

    def _load(self):
        if not os.path.exists(self.path):
            return json.loads(json.dumps(DEFAULT_STATE))
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                state = json.load(handle)
        except (ValueError, OSError):
            return json.loads(json.dumps(DEFAULT_STATE))
        for key, value in DEFAULT_STATE.items():
            state.setdefault(key, json.loads(json.dumps(value)))
        return state

    def save(self):
        directory = os.path.dirname(os.path.abspath(self.path))
        if directory and not os.path.isdir(directory):
            os.makedirs(directory)
        handle = tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=directory, delete=False, suffix=".tmp",
        )
        try:
            json.dump(self.state, handle, indent=1, sort_keys=True, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        finally:
            handle.close()
        os.replace(handle.name, self.path)

    # ------------------------------------------------------------- records --
    def known(self, post_id):
        return post_id in self.state["posts"]

    def get(self, post_id):
        return self.state["posts"].get(post_id)

    def upsert(self, record):
        existing = self.state["posts"].get(record["id"])
        if existing:
            record["first_seen"] = existing.get("first_seen", record.get("first_seen"))
            # keep the highest score/comments we ever observed
            for key in ("score", "comments"):
                old, new = existing.get(key), record.get(key)
                if new is None or (old is not None and old > new):
                    record[key] = old
            record["is_new"] = False
        else:
            record["is_new"] = True
        record["last_seen"] = _now_iso()
        self.state["posts"][record["id"]] = record
        return record

    def posts(self):
        return list(self.state["posts"].values())

    # -------------------------------------------------------------- alerts --
    def already_alerted(self, post_id):
        return post_id in self.state["alerted"]

    def mark_alerted(self, post_ids):
        stamp = _now_iso()
        for post_id in post_ids:
            self.state["alerted"][post_id] = stamp

    # ----------------------------------------------------------- retention --
    def prune(self, keep_days):
        cutoff = _now_epoch() - keep_days * 86400
        kept = {}
        for post_id, record in self.state["posts"].items():
            created = record.get("created_utc") or 0
            if created >= cutoff:
                kept[post_id] = record
        removed = len(self.state["posts"]) - len(kept)
        self.state["posts"] = kept
        self.state["alerted"] = {
            k: v for k, v in self.state["alerted"].items() if k in kept
        }
        return removed

    # --------------------------------------------------------------- audit --
    def record_run(self, summary):
        self.state["runs"].append(summary)
        self.state["runs"] = self.state["runs"][-40:]


def _now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _now_epoch():
    return int(datetime.now(timezone.utc).timestamp())

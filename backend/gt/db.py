"""MongoDB store: one collection per schema dataclass, _id = first field."""
import dataclasses
import typing

import mongomock
from pymongo import MongoClient, ReplaceOne
from pymongo.database import Database

from gt import schema
from gt.config import DB_NAME, env


def connect(uri: str | None = None, name: str = DB_NAME) -> Database:
    uri = uri if uri is not None else env("MONGODB_URI")
    if not uri or uri.startswith("mongomock://"):
        return mongomock.MongoClient()[name]
    return MongoClient(uri)[name]


def _coll(cls: type) -> str:
    return cls.__name__.lower()


def insert(conn: Database, rows: list) -> int:
    if not rows:
        return 0
    cls = type(rows[0])
    key = dataclasses.fields(cls)[0].name
    docs = [{"_id": getattr(r, key), **dataclasses.asdict(r)} for r in rows]
    coll = conn[_coll(cls)]
    if isinstance(conn.client, mongomock.MongoClient):
        # mongomock 4.3 rejects pymongo's ReplaceOne in bulk_write, and per-row replace_one is O(n) each
        # (9k transfers took 52 s) — so upsert as one delete + one insert. Last row wins on duplicate ids.
        docs = list({d["_id"]: d for d in docs}.values())
        coll.delete_many({"_id": {"$in": [d["_id"] for d in docs]}})
        coll.insert_many(docs)
    else:
        coll.bulk_write([ReplaceOne({"_id": d["_id"]}, d, upsert=True) for d in docs], ordered=False)
    return len(rows)


def select(conn: Database, cls: type, query: dict | None = None) -> list:
    nested = {f.name: typing.get_args(f.type)[0] for f in dataclasses.fields(cls)
              if typing.get_args(f.type) and dataclasses.is_dataclass(typing.get_args(f.type)[0])}
    out = []
    for doc in conn[_coll(cls)].find(query or {}):
        doc.pop("_id", None)
        for name, sub in nested.items():
            doc[name] = [sub(**x) for x in doc.get(name, [])]
        out.append(cls(**doc))
    return out


def clear(conn: Database) -> None:
    for cls in schema.ALL:
        conn.drop_collection(_coll(cls))


def put_meta(conn: Database, key: str, value) -> None:
    conn.meta.replace_one({"_id": key}, {"_id": key, "value": value}, upsert=True)


def get_meta(conn: Database, key: str, default=None):
    doc = conn.meta.find_one({"_id": key})
    return doc["value"] if doc else default

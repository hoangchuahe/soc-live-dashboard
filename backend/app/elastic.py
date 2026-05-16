"""
Optional ElasticSearch integration.
The app runs fine without ES — this module silently no-ops when ES is unreachable.

Enable with:  docker compose --profile elastic up
Query index:  GET http://localhost:9200/soc-events/_search
"""

import asyncio
import os

ES_URL = os.getenv("ELASTICSEARCH_URL", "http://elasticsearch:9200")
INDEX = "soc-events"

_client = None
_available = False


async def _init():
    global _client, _available
    try:
        from elasticsearch import AsyncElasticsearch
        _client = AsyncElasticsearch(ES_URL, request_timeout=5)
        await _client.info()

        if not await _client.indices.exists(index=INDEX):
            await _client.indices.create(
                index=INDEX,
                body={
                    "mappings": {
                        "properties": {
                            "timestamp":      {"type": "date"},
                            "type":           {"type": "keyword"},
                            "severity":       {"type": "keyword"},
                            "source_ip":      {"type": "ip"},
                            "source_country": {"type": "keyword"},
                            "tactic":         {"type": "keyword"},
                            "technique_id":   {"type": "keyword"},
                            "event_id":       {"type": "integer"},
                            "hostname":       {"type": "keyword"},
                            "message":        {"type": "text"},
                        }
                    }
                },
            )
        _available = True
        print(f"[elastic] connected — indexing to '{INDEX}'")
    except Exception as exc:
        _available = False
        print(f"[elastic] not available ({exc.__class__.__name__}) — running without ES")


async def startup():
    asyncio.create_task(_init())


async def index_event(event: dict) -> None:
    if not _available or _client is None:
        return
    try:
        await _client.index(index=INDEX, document=event)
    except Exception:
        pass


async def search(query: str, size: int = 20) -> list[dict]:
    if not _available or _client is None:
        return []
    try:
        resp = await _client.search(
            index=INDEX,
            body={
                "size": size,
                "sort": [{"timestamp": {"order": "desc"}}],
                "query": {
                    "multi_match": {
                        "query": query,
                        "fields": ["message", "type", "source_ip", "hostname", "tactic"],
                    }
                },
            },
        )
        return [hit["_source"] for hit in resp["hits"]["hits"]]
    except Exception:
        return []


def is_available() -> bool:
    return _available

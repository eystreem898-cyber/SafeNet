import logging
from typing import Any, Dict, List, Optional

from bot.config import settings

try:
    from motor.motor_asyncio import AsyncIOMotorClient
except ImportError:  # pragma: no cover - runtime safety
    AsyncIOMotorClient = None

try:
    from redis.asyncio import Redis
except ImportError:  # pragma: no cover - runtime safety
    Redis = None

logger = logging.getLogger("safenet.database")


class DatabaseManager:
    def __init__(self) -> None:
        self.client: Optional[Any] = None
        self.db: Optional[Any] = None
        self.redis: Optional[Any] = None
        self.fallback: Dict[str, List[Dict[str, Any]]] = {}
        self._connected = False

    async def connect(self) -> None:
        if self._connected:
            return

        if AsyncIOMotorClient is not None:
            try:
                self.client = AsyncIOMotorClient(settings.mongodb_uri, serverSelectionTimeoutMS=3000)
                self.db = self.client[settings.mongodb_db]
                await self.client.admin.command("ping")
                logger.info("MongoDB connected")
            except Exception as exc:
                logger.warning("Failed to connect to MongoDB: %s", exc)
                self.db = None
        else:
            logger.warning("Motor is not installed; using in-memory Mongo fallback")

        if Redis is not None:
            try:
                self.redis = Redis.from_url(settings.redis_url, decode_responses=True)
                await self.redis.ping()
                logger.info("Redis connected")
            except Exception as exc:
                logger.warning("Failed to connect to Redis: %s", exc)
                self.redis = None
        else:
            logger.warning("Redis async client is not installed; caching disabled")

        self._connected = True

    async def close(self) -> None:
        if self.redis is not None:
            try:
                await self.redis.close()
            except Exception:
                pass
        if self.client is not None:
            self.client.close()
        self._connected = False

    async def ping(self) -> bool:
        if not self._connected:
            return False
        try:
            if self.client is not None:
                await self.client.admin.command("ping")
            if self.redis is not None:
                await self.redis.ping()
            return True
        except Exception:
            return False

    async def save_document(self, collection: str, payload: Dict[str, Any]) -> None:
        if self.db is None:
            self.fallback.setdefault(collection, []).append(payload)
            return
        await self.db[collection].insert_one(payload)

    async def get_documents(self, collection: str, query: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        query = query or {}
        if self.db is None:
            return [doc for doc in self.fallback.get(collection, []) if all(doc.get(k) == v for k, v in query.items())]
        cursor = self.db[collection].find(query)
        return [doc async for doc in cursor]

    async def find_one(self, collection: str, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if self.db is None:
            for doc in self.fallback.get(collection, []):
                if all(doc.get(k) == v for k, v in query.items()):
                    return doc
            return None
        return await self.db[collection].find_one(query)

    async def update_document(self, collection: str, query: Dict[str, Any], update: Dict[str, Any]) -> None:
        if self.db is None:
            for doc in self.fallback.get(collection, []):
                if all(doc.get(k) == v for k, v in query.items()):
                    doc.update(update)
            return
        await self.db[collection].update_one(query, {"$set": update}, upsert=False)

    async def delete_document(self, collection: str, query: Dict[str, Any]) -> None:
        if self.db is None:
            self.fallback[collection] = [doc for doc in self.fallback.get(collection, []) if not all(doc.get(k) == v for k, v in query.items())]
            return
        await self.db[collection].delete_many(query)

    async def cache_set(self, key: str, value: Any, expire: int = 300) -> None:
        if self.redis is None:
            self.fallback[key] = value
            return
        await self.redis.set(key, value, ex=expire)

    async def cache_get(self, key: str) -> Any:
        if self.redis is None:
            return self.fallback.get(key)
        return await self.redis.get(key)

    async def cache_delete(self, key: str) -> None:
        if self.redis is None:
            self.fallback.pop(key, None)
            return
        await self.redis.delete(key)

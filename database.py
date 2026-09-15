from motor.motor_asyncio import AsyncIOMotorClient

class DatabaseManager:
    client: AsyncIOMotorClient = None
    db = None
    channels = None

    @classmethod
    def connect(cls):
        cls.client = AsyncIOMotorClient("mongodb://localhost:27017")
        cls.db = cls.client.atlas_db
        cls.channels = cls.db.channels

    @classmethod
    def close(cls):
        if cls.client:
            cls.client.close()

db_manager = DatabaseManager()

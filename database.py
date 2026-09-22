from motor.motor_asyncio import AsyncIOMotorClient

class DatabaseManager:
    client: AsyncIOMotorClient = None
    db = None
    channels = None
    messages = None

    @classmethod
    def connect(cls):
        cls.client = AsyncIOMotorClient("mongodb://localhost:27017")
        cls.db = cls.client.atlas_db
        cls.channels = cls.db.channels
        cls.messages = cls.db.messages

    @classmethod
    def close(cls):
        if cls.client:
            cls.client.close()

db_manager = DatabaseManager()

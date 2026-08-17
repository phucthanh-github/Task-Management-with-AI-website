import logging
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError, PyMongoError
from .config import settings

logger = logging.getLogger("todolist_api")

class Database:
    client: AsyncIOMotorClient = None
    db = None

db_helper = Database()

def get_db():
    return db_helper.db

def get_client():
    return db_helper.client

async def init_indexes():
    if db_helper.db is None:
        logger.warning("[MongoDB Index] Skipped initialization: database instance is None.")
        return

    db = db_helper.db

    # 1. unique: users.email
    try:
        await db.users.create_index([("email", 1)], unique=True)
        logger.info("[MongoDB Index] Created/Verified unique index on users.email")
    except DuplicateKeyError as e:
        logger.error(
            f"[MongoDB Index Migration Note] Failed to create unique index on 'users.email': "
            f"Existing duplicate emails detected in database. Error: {e}. "
            f"Please clean up duplicate records manually before retrying index creation."
        )
    except PyMongoError as e:
        logger.error(f"[MongoDB Index Error] Failed to create index on users.email: {e}")

    # 2. todos: { user_id: 1, created_at: -1 }
    try:
        await db.todos.create_index([("user_id", 1), ("created_at", -1)])
        logger.info("[MongoDB Index] Created/Verified index on todos(user_id, created_at)")
    except PyMongoError as e:
        logger.error(f"[MongoDB Index Error] Failed to create index on todos(user_id, created_at): {e}")

    # 3. todos: { user_id: 1, status: 1, deadline: 1 }
    try:
        await db.todos.create_index([("user_id", 1), ("status", 1), ("deadline", 1)])
        logger.info("[MongoDB Index] Created/Verified index on todos(user_id, status, deadline)")
    except PyMongoError as e:
        logger.error(f"[MongoDB Index Error] Failed to create index on todos(user_id, status, deadline): {e}")

    # 4. chat_messages: { user_id: 1, timestamp: -1 }
    try:
        await db.chat_messages.create_index([("user_id", 1), ("timestamp", -1)])
        logger.info("[MongoDB Index] Created/Verified index on chat_messages(user_id, timestamp)")
    except PyMongoError as e:
        logger.error(f"[MongoDB Index Error] Failed to create index on chat_messages(user_id, timestamp): {e}")

async def connect_to_mongo():
    db_helper.client = AsyncIOMotorClient(settings.MONGODB_URL)
    db_helper.db = db_helper.client[settings.MONGODB_DB_NAME]
    
    # Simple check connection
    try:
        await db_helper.client.admin.command('ping')
        logger.info(f"Successfully connected to MongoDB at: {settings.MONGODB_URL.split('@')[-1] if '@' in settings.MONGODB_URL else settings.MONGODB_URL}")
        await init_indexes()
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        logger.error("Please check if MongoDB is running and settings.MONGODB_URL is correct.")

async def close_mongo_connection():
    if db_helper.client:
        db_helper.client.close()
        logger.info("MongoDB connection closed")


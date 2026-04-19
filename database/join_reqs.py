import motor.motor_asyncio
from info import REQ_CHANNEL_1, REQ_CHANNEL_2

class JoinReqs:
    _instance = None  # Singleton instance

    def __new__(cls):
        """Reuse a single instance to avoid creating new MongoDB connections on every call"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        from info import JOIN_REQS_DB
        if JOIN_REQS_DB:
            self.client = motor.motor_asyncio.AsyncIOMotorClient(JOIN_REQS_DB)
            self.db = self.client["JoinReqs"]
            self.col1 = self.db[str(REQ_CHANNEL_1)]
            self.col2 = self.db[str(REQ_CHANNEL_2)]
        else:
            self.client = None
            self.db = None
            self.col1 = None
            self.col2 = None
        self._initialized = True

    def isActive(self):
        return self.client is not None

    async def add_user(self, user_id, first_name, username, date, channel=None):
        try:
            if channel == 1:
                await self.col1.insert_one({"_id": int(user_id), "user_id": int(user_id), "first_name": first_name, "username": username, "date": date})
            elif channel == 2:
                await self.col2.insert_one({"_id": int(user_id), "user_id": int(user_id), "first_name": first_name, "username": username, "date": date})
        except:
            pass
            

    async def get_user(self, user_id, channel=None):
        # Query by _id (primary index) for maximum speed
        if channel == 1:
            return await self.col1.find_one({"_id": int(user_id)})
        elif channel == 2:
            return await self.col2.find_one({"_id": int(user_id)})

    async def delete_user(self, user_id, channel=None):
        if channel == 1:
            await self.col1.delete_one({"_id": int(user_id)})
        elif channel == 2:
            await self.col2.delete_one({"_id": int(user_id)})

    async def delete_all_users(self, channel=None):
        if channel == 1:
            await self.col1.delete_many({})
        elif channel == 2:
            await self.col2.delete_many({})

    async def get_all_users_count(self, channel=None):
        if channel == 1:
            return await self.col1.count_documents({})
        elif channel == 2:
            return await self.col2.count_documents({})

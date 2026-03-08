import sqlite3
import asyncio
from datetime import datetime
from typing import Optional, Dict, List

class Database:
    def __init__(self, db_path: str = "bot.db"):
        self.db_path = db_path
    
    async def init_db(self):
        """Инициализация базы данных"""
        def _init_db():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    balance INTEGER DEFAULT 1000,
                    bank_balance INTEGER DEFAULT 0,
                    registration_date TEXT,
                    avatar_path TEXT,
                    is_banned BOOLEAN DEFAULT FALSE,
                    profile_closed BOOLEAN DEFAULT FALSE,
                    daily_winnings INTEGER DEFAULT 0,
                    last_bonus_date TEXT
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_user_id INTEGER,
                    to_user_id INTEGER,
                    amount INTEGER,
                    transaction_type TEXT,
                    timestamp TEXT
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS game_settings (
                    game_name TEXT PRIMARY KEY,
                    is_enabled BOOLEAN DEFAULT TRUE
                )
            """)
            
            conn.commit()
            conn.close()
        
        # Выполняем в отдельном потоке
        await asyncio.get_event_loop().run_in_executor(None, _init_db)
    
    async def add_user(self, user_id: int, username: str, first_name: str, last_name: str = None):
        """Добавление нового пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR IGNORE INTO users 
                (user_id, username, first_name, last_name, registration_date)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, username, first_name, last_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            await db.commit()
    
    async def get_user(self, user_id: int) -> Optional[Dict]:
        """Получение информации о пользователе"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    columns = [description[0] for description in cursor.description]
                    return dict(zip(columns, row))
                return None
    
    async def update_balance(self, user_id: int, amount: int) -> bool:
        """Обновление баланса пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
            await db.commit()
            return cursor.rowcount > 0
    
    async def update_bank_balance(self, user_id: int, amount: int) -> bool:
        """Обновление банковского баланса"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("UPDATE users SET bank_balance = bank_balance + ? WHERE user_id = ?", (amount, user_id))
            await db.commit()
            return cursor.rowcount > 0
    
    async def transfer_money(self, from_user_id: int, to_user_id: int, amount: int) -> bool:
        """Перевод денег между пользователями"""
        async with aiosqlite.connect(self.db_path) as db:
            # Проверяем баланс отправителя
            async with db.execute("SELECT balance FROM users WHERE user_id = ?", (from_user_id,)) as cursor:
                row = await cursor.fetchone()
                if not row or row[0] < amount:
                    return False
            
            # Выполняем перевод
            await db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, from_user_id))
            await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, to_user_id))
            
            # Записываем транзакцию
            await db.execute("""
                INSERT INTO transactions (from_user_id, to_user_id, amount, transaction_type, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (from_user_id, to_user_id, amount, "transfer", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            
            await db.commit()
            return True
    
    async def get_top_users(self, limit: int = 10) -> List[Dict]:
        """Получение топ пользователей по балансу"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT user_id, username, first_name, balance 
                FROM users 
                WHERE is_banned = FALSE 
                ORDER BY balance DESC 
                LIMIT ?
            """, (limit,)) as cursor:
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
    
    async def get_top_banks(self, limit: int = 10) -> List[Dict]:
        """Получение топ банков"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT user_id, username, first_name, bank_balance 
                FROM users 
                WHERE is_banned = FALSE AND bank_balance > 0
                ORDER BY bank_balance DESC 
                LIMIT ?
            """, (limit,)) as cursor:
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
    
    async def ban_user(self, user_id: int) -> bool:
        """Бан пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("UPDATE users SET is_banned = TRUE WHERE user_id = ?", (user_id,))
            await db.commit()
            return cursor.rowcount > 0
    
    async def unban_user(self, user_id: int) -> bool:
        """Разбан пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("UPDATE users SET is_banned = FALSE WHERE user_id = ?", (user_id,))
            await db.commit()
            return cursor.rowcount > 0
    
    async def update_avatar(self, user_id: int, avatar_path: str) -> bool:
        """Обновление аватара"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("UPDATE users SET avatar_path = ? WHERE user_id = ?", (avatar_path, user_id))
            await db.commit()
            return cursor.rowcount > 0
    
    async def toggle_profile(self, user_id: int, closed: bool) -> bool:
        """Закрыть/открыть профиль"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("UPDATE users SET profile_closed = ? WHERE user_id = ?", (closed, user_id))
            await db.commit()
            return cursor.rowcount > 0
    
    async def update_daily_winnings(self, user_id: int, amount: int) -> bool:
        """Обновление дневных выигрышей"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("UPDATE users SET daily_winnings = daily_winnings + ? WHERE user_id = ?", (amount, user_id))
            await db.commit()
            return cursor.rowcount > 0
    
    async def reset_daily_winnings(self):
        """Сброс дневных выигрышей (выполняется в 00:00)"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET daily_winnings = 0")
            await db.commit()
    
    async def get_leaderboard(self, limit: int = 5) -> List[Dict]:
        """Получение лидерборда"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT user_id, username, first_name, daily_winnings 
                FROM users 
                WHERE is_banned = FALSE AND daily_winnings > 0
                ORDER BY daily_winnings DESC 
                LIMIT ?
            """, (limit,)) as cursor:
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
    
    async def get_game_settings(self) -> Dict[str, bool]:
        """Получение настроек игр"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT game_name, is_enabled FROM game_settings") as cursor:
                rows = await cursor.fetchall()
                return {row[0]: bool(row[1]) for row in rows}
    
    async def toggle_game(self, game_name: str, enabled: bool) -> bool:
        """Включить/отключить игру"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO game_settings (game_name, is_enabled)
                VALUES (?, ?)
            """, (game_name, enabled))
            await db.commit()
            return True

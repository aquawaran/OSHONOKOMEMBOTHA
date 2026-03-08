import random
import asyncio
from typing import Dict, Optional, List
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

class TradeGame:
    """Игра Трейд - угадывание направления графика"""
    
    def __init__(self, database):
        self.db = database
        self.active_games: Dict[int, Dict] = {}  # user_id -> game_data
        
        # Параметры игры
        self.multipliers = {
            "up": [1.3, 1.5, 1.8, 2.0, 2.5],  # Множители для роста
            "down": [1.3, 1.5, 1.8, 2.0, 2.5]  # Множители для падения
        }
    
    async def start_game(self, message: Message, bet: int, direction: str) -> bool:
        """Начать игру трейд"""
        user_id = message.from_user.id
        user = await self.db.get_user(user_id)
        
        if not user or user['balance'] < bet:
            await message.reply("❌ Недостаточно MEM для ставки")
            return False
        
        if bet < 100:
            await message.reply("❌ Минимальная ставка: 100 MEM")
            return False
        
        # Списываем ставку
        await self.db.update_balance(user_id, -bet)
        
        # Генерируем график
        graph_data = self._generate_graph(direction)
        multiplier = random.choice(self.multipliers[direction])
        
        # Сохраняем игру
        self.active_games[user_id] = {
            'bet': bet,
            'direction': direction,
            'multiplier': multiplier,
            'graph_data': graph_data,
            'revealed': False
        }
        
        # Отправляем график
        await self._send_graph(message, user_id, show_result=False)
        return True
    
    def _generate_graph(self, correct_direction: str) -> List[int]:
        """Сгенерировать данные графика"""
        # Базовая точка
        base = 100
        data = [base]
        
        # Генерируем точки с учетом правильного направления
        for i in range(8):
            if i < 6:  # Первые 6 точек - относительно случайные
                change = random.randint(-15, 15)
            else:  # Последние 2 точки - обеспечиваем правильное направление
                if correct_direction == "up":
                    change = random.randint(5, 20)
                else:
                    change = random.randint(-20, -5)
            
            new_point = max(20, min(180, data[-1] + change))
            data.append(new_point)
        
        return data
    
    async def _send_graph(self, message: Message, user_id: int, show_result: bool = False):
        """Отправить результат трейда"""
        game = self.active_games.get(user_id)
        if not game:
            return
        
        direction = "📈 Рост" if game['direction'] == "up" else "📉 Падение"
        
        if show_result:
            win_amount = int(game['bet'] * game['multiplier'])
            await self.db.update_balance(user_id, win_amount)
            await self.db.update_daily_winnings(user_id, win_amount - game['bet'])
            
            # Только ставка, направление и результат
            status_text = f"📊 Трейд\n\n"
            status_text += f"💰 Ставка: {game['bet']} MEM\n"
            status_text += f"📈 Направление: {direction}\n"
            status_text += f"🎉 Выигрыш: {win_amount} MEM"
            
            await message.reply(status_text, reply_to_message_id=message.message_id)
            del self.active_games[user_id]
        else:
            # Показываем выбор и через 1 секунду результат
            status_text = f"📊 Трейд\n\n"
            status_text += f"💰 Ставка: {game['bet']} MEM\n"
            status_text += f"🤔 Выбор: {direction}\n"
            status_text += f"⏳ Ожидание результата..."
            
            await message.reply(status_text, reply_to_message_id=message.message_id)
            await asyncio.sleep(1)
            await self._reveal_result(message, user_id)
    
    def _create_graph_visual(self, data: List[int]) -> str:
        """Создать визуальное представление графика"""
        # Высота графика в символах
        height = 10
        width = len(data) - 1
        
        # Нормализуем данные
        min_val = min(data)
        max_val = max(data)
        range_val = max_val - min_val
        
        if range_val == 0:
            range_val = 1
        
        # Создаем сетку
        grid = [[" " for _ in range(width + 1)] for _ in range(height)]
        
        # Размещаем точки на графике
        for i, value in enumerate(data):
            x = i
            y = height - 1 - int((value - min_val) / range_val * (height - 1))
            y = max(0, min(height - 1, y))
            grid[y][x] = "●"
        
        # Соединяем точки линиями
        for i in range(len(data) - 1):
            x1, y1 = i, height - 1 - int((data[i] - min_val) / range_val * (height - 1))
            x2, y2 = i + 1, height - 1 - int((data[i + 1] - min_val) / range_val * (height - 1))
            
            y1 = max(0, min(height - 1, y1))
            y2 = max(0, min(height - 1, y2))
            
            # Простая линия между точками
            if y1 == y2:
                for x in range(min(x1, x2), max(x1, x2) + 1):
                    if 0 <= x < width + 1:
                        grid[y1][x] = "─"
            elif y1 < y2:
                for y in range(y1, y2 + 1):
                    if 0 <= y < height:
                        grid[y][x1] = "│"
            else:
                for y in range(y2, y1 + 1):
                    if 0 <= y < height:
                        grid[y][x1] = "│"
        
        # Возвращаем точки обратно
        for i, value in enumerate(data):
            x = i
            y = height - 1 - int((value - min_val) / range_val * (height - 1))
            y = max(0, min(height - 1, y))
            grid[y][x] = "●"
        
        # Собираем график в строку
        graph_lines = []
        for row in grid:
            graph_lines.append("".join(row))
        
        # Добавляем оси
        graph_lines.append("└" + "─" * width)
        
        return "```\n" + "\n".join(graph_lines) + "\n```"
    
    async def _reveal_result(self, message: Message, user_id: int):
        """Показать результат игры"""
        game = self.active_games.get(user_id)
        if not game:
            return
        
        win_amount = int(game['bet'] * game['multiplier'])
        await self.db.update_balance(user_id, win_amount)
        await self.db.update_daily_winnings(user_id, win_amount - game['bet'])
        
        await self._send_graph(message, user_id, show_result=True)
    
    def get_rules(self) -> str:
        """Получить правила игры"""
        rules = "📊 ТРЕЙД\n\n"
        rules += "📜 Правила:\n"
        rules += "• Минимальная ставка: 100 MEM\n"
        rules += "• Нужно угадать направление графика\n"
        rules += "• График покажет реальное направление\n\n"
        rules += "🎯 Команды:\n"
        rules += "• Трейдап [ставка] - ставка на рост 📈\n"
        rules += "• Трейдовн [ставка] - ставка на падение 📉\n\n"
        rules += "💰 Множители:\n"
        rules += "• Возможный выигрыш: x1.3 - x2.5\n"
        rules += "• Чем точнее угадано направление, тем выше множитель"
        
        return rules

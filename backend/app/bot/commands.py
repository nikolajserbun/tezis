from __future__ import annotations

from aiogram.types import BotCommand

COMMANDS = [
    BotCommand(command="start", description="Запуск и настройка"),
    BotCommand(command="menu", description="Главное меню"),
    BotCommand(command="profile", description="Личный кабинет"),
    BotCommand(command="shop", description="Магазин и тарифы"),
    BotCommand(command="chat", description="Чат с ИИ"),
    BotCommand(command="subscription", description="Моя подписка"),
    BotCommand(command="balance", description="Баланс и реферальные"),
    BotCommand(command="referral", description="Реферальная программа"),
    BotCommand(command="support", description="Поддержка"),
    BotCommand(command="help", description="Справка"),
]

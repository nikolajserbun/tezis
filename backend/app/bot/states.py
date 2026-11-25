from aiogram.fsm.state import State, StatesGroup


class Onboarding(StatesGroup):
    niche = State()
    audience = State()
    tone = State()
    goals = State()


class Content(StatesGroup):
    topic = State()


class Chat(StatesGroup):
    message = State()


class Support(StatesGroup):
    message = State()


class Payout(StatesGroup):
    amount = State()
    requisites = State()

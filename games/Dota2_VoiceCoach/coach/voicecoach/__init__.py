"""Голосовой тренер Dota 2: разбор речи тренера в команды агентам."""
from .protocol import ACTIONS, Command, PROTOCOL_VERSION, validate
from .parser import Agent, MatchContext, ParseResult, parse, normalize

__all__ = ["ACTIONS", "Command", "PROTOCOL_VERSION", "validate",
           "Agent", "MatchContext", "ParseResult", "parse", "normalize"]

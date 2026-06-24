"""
app/services/credits_service.py — Motor de créditos Pay-as-you-go.

Migrado y limpiado desde credits_engine.py.
Rutas ahora usan app.config.
"""

import json
import os
from datetime import datetime
from typing import Optional

from app.config import config

# ============================================================
# CONFIGURACIÓN DE PRECIOS
# ============================================================

COST_PER_1K_TOKENS_USD = 0.00015
MARGIN_MULTIPLIER = 10
USD_TO_CREDITS = 100

AVG_TOKENS_PER_AGENT = 1500
BASE_COST_PER_AGENT_USD = (AVG_TOKENS_PER_AGENT / 1000) * COST_PER_1K_TOKENS_USD
CREDIT_COST_PER_AGENT = BASE_COST_PER_AGENT_USD * MARGIN_MULTIPLIER * USD_TO_CREDITS

# Tipos de operación (research only)
OP_SIMULATION = "Simulación de estudio (1 agente)"
OP_GENESIS = "Génesis de Audiencia"
OP_REPORT = "Generación de Reporte"

CREDIT_TABLE = {
    OP_SIMULATION: round(CREDIT_COST_PER_AGENT, 4),
    OP_GENESIS: 5.0,
    OP_REPORT: 10.0,
}


class CreditsService:
    """Motor de créditos Pay-as-you-go para Predikpedia."""

    def __init__(self, user_id: str = "default_user"):
        self.user_id = user_id
        self.ledger_file = str(config.ledger_file)
        self._ensure_ledger()

    def _ensure_ledger(self):
        os.makedirs(os.path.dirname(self.ledger_file), exist_ok=True)
        if not os.path.exists(self.ledger_file):
            self._save_ledger({"users": {}})

    def _load_ledger(self) -> dict:
        try:
            with open(self.ledger_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"users": {}}

    def _save_ledger(self, data: dict):
        with open(self.ledger_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def _get_user_record(self, ledger: dict) -> dict:
        if self.user_id not in ledger["users"]:
            ledger["users"][self.user_id] = {
                "balance_credits": 0.0,
                "total_loaded_usd": 0.0,
                "total_consumed_credits": 0.0,
                "transactions": [],
            }
        return ledger["users"][self.user_id]

    def load_balance(self, usd_amount: float) -> dict:
        """Convierte USD a Predik-Credits y los acredita."""
        if usd_amount <= 0:
            return {"ok": False, "error": "Monto inválido"}

        credits_to_add = usd_amount * USD_TO_CREDITS
        ledger = self._load_ledger()
        user = self._get_user_record(ledger)

        user["balance_credits"] += credits_to_add
        user["total_loaded_usd"] += usd_amount
        user["transactions"].append({
            "type": "CARGA",
            "usd": usd_amount,
            "credits": credits_to_add,
            "balance_after": user["balance_credits"],
            "ts": datetime.now().isoformat(),
        })

        self._save_ledger(ledger)
        return {
            "ok": True,
            "credits_added": credits_to_add,
            "new_balance": user["balance_credits"],
        }

    def consume(self, operation: str, quantity: int = 1) -> dict:
        """Descuenta créditos por operación."""
        cost_per_unit = CREDIT_TABLE.get(operation, CREDIT_COST_PER_AGENT)
        total_cost = cost_per_unit * quantity

        ledger = self._load_ledger()
        user = self._get_user_record(ledger)

        if user["balance_credits"] < total_cost:
            return {
                "ok": False,
                "error": "Saldo insuficiente",
                "needed": total_cost,
                "balance": user["balance_credits"],
            }

        user["balance_credits"] -= total_cost
        user["total_consumed_credits"] += total_cost
        user["transactions"].append({
            "type": "CONSUMO",
            "operation": operation,
            "quantity": quantity,
            "credits_deducted": total_cost,
            "balance_after": user["balance_credits"],
            "ts": datetime.now().isoformat(),
        })

        self._save_ledger(ledger)
        return {
            "ok": True,
            "credits_deducted": total_cost,
            "new_balance": user["balance_credits"],
        }

    def get_balance(self) -> float:
        ledger = self._load_ledger()
        user = self._get_user_record(ledger)
        return user["balance_credits"]

    def get_balance_usd_equiv(self) -> float:
        return self.get_balance() / USD_TO_CREDITS

    def get_history(self, last_n: int = 20) -> list:
        ledger = self._load_ledger()
        user = self._get_user_record(ledger)
        return user["transactions"][-last_n:]

    def get_pricing_table(self) -> dict:
        return {
            op: {
                "credits": cost,
                "usd_equiv": round(cost / USD_TO_CREDITS, 6),
            }
            for op, cost in CREDIT_TABLE.items()
        }

    def estimate_study_cost(self, num_agents: int) -> dict:
        cost_credits = CREDIT_TABLE[OP_SIMULATION] * num_agents
        return {
            "agents": num_agents,
            "cost_credits": round(cost_credits, 2),
            "cost_usd_equiv": round(cost_credits / USD_TO_CREDITS, 4),
            "balance": self.get_balance(),
            "can_run": self.get_balance() >= cost_credits,
        }

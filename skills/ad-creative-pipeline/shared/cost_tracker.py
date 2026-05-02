"""
AdCreativePipeline — 成本追踪器 (P0-2)
防止账单失控：预算上限 + 实时计数 + 超支阻止
"""

from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class CostTracker:
    """单次 Pipeline 成本追踪"""
    budget_yuan: float = 5.0
    spent_yuan: float = 0.0
    history: list = field(default_factory=list)

    def check_and_charge(self, provider_name: str, count: int = 1,
                         cost_per_image: float = 0.04) -> bool:
        """
        检查预算并扣费
        Returns: True=通过, 抛出 BudgetExceededError=超支
        """
        charge = count * cost_per_image
        if self.spent_yuan + charge > self.budget_yuan:
            raise BudgetExceededError(
                f"超出预算! 已花费 ¥{self.spent_yuan:.2f} + "
                f"本次 ¥{charge:.2f} > 预算 ¥{self.budget_yuan:.2f}\n"
                f"提示: 调高预算 (--budget N) 或减少概念数 (--concepts N)"
            )

        self.spent_yuan += charge
        self.history.append({
            "provider": provider_name,
            "count": count,
            "cost": charge,
            "timestamp": datetime.now().isoformat()
        })
        return True

    def summary(self) -> str:
        return (
            f"💰 费用: ¥{self.spent_yuan:.2f} / ¥{self.budget_yuan:.2f} "
            f"({self.spent_yuan/self.budget_yuan*100:.0f}%)"
        )

    def remaining(self) -> float:
        return self.budget_yuan - self.spent_yuan


class BudgetExceededError(Exception):
    pass

# avoid_aoe_decision.py

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ares.behaviors.combat.individual import CombatIndividualBehavior
from ares.managers.manager_mediator import ManagerMediator
from ares.consts import UnitTreeQueryType
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.unit import Unit
from sc2.units import Units

if TYPE_CHECKING:
    from ares import AresBot

@dataclass
class AvoidAOEDecision(CombatIndividualBehavior):
    """Avoid Incoming AOE Effects

    """

    def execute(self, ai: "AresBot", config: dict, mediator: ManagerMediator) -> bool:
        """Execute the Avoid AOE macro behavior."""

        # TODO: implement this
        return False

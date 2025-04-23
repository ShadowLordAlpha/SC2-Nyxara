# group_priority_attack.py
"""
Sets the Unit to attack a target from a group of targets based on priority and other units in the area
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from s2clientprotocol.common_pb2 import Point
from sc2.ids.ability_id import AbilityId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from ares.behaviors.combat.group import CombatGroupBehavior
from ares.managers.manager_mediator import ManagerMediator

if TYPE_CHECKING:
    from ares import AresBot


@dataclass
class GroupPriorityAttack(CombatGroupBehavior):
    """
    Use the group to attack specific units based on priority and what units can actually be attacked.
    """

    forces: Units

    def execute(self, ai: "AresBot", config: dict, mediator: ManagerMediator) -> bool:
        """Execute the Priority Attack Behavior"""

        # If we don't have any forces, do nothing
        if len(self.forces) == 0:
            return False


# group_a_move.py
"""
Attack move with a group of units. This automatically filters out duplicate commands but will reissue the command to
individual units as needed. It will not reissue commands to units that don't need them, even if other units in the group
do need the command.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Union

from cython_extensions import cy_sorted_by_distance_to
from sc2.ids.ability_id import AbilityId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from ares.behaviors.combat.group.combat_group_behavior import CombatGroupBehavior
from ares.managers.manager_mediator import ManagerMediator

if TYPE_CHECKING:
    from ares import AresBot

@dataclass
class GroupAMove(CombatGroupBehavior):
    """A-Move group to a target.

    Attributes:
        group (list[Unit] | Units): Units we want to control.
        target (Point2 | Unit): Where the unit is going.
    """

    group: Union[Units, list[Unit]]
    target: Union[Point2, Unit]

    def execute(self, ai: "AresBot", config: dict, mediator: ManagerMediator) -> bool:
        if len(self.group) == 0:
            return False

        needs_order : set[int] = set()
        for unit in self.group:
            if not self.duplicate_or_similar_order(unit, self.target, AbilityId.ATTACK):
                needs_order.add(unit.tag)

        if needs_order:
            ai.give_same_action(AbilityId.ATTACK, needs_order, self.target)
            return True

        return False

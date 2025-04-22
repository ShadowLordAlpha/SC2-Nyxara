# group_up.py
"""
Collect all units in a given area
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
class GroupUp(CombatGroupBehavior):
    """
    Collect all units in a given area

    ```py
    TODO: Example here
    ```

    Attributes:
        group (list[Unit]): Units we want to control.
        target (Point2): Where we are grouping up the units
    """

    group: Units
    target: Point2

    def execute(self, ai: "AresBot", config: dict, mediator: ManagerMediator) -> bool:
        """Execute the GroupUp behavior."""
        if len(self.group) == 0:
            return False

        # Get the average radius of all units in the group
        radius_needed = len(self.group) / (sum(g.radius for g in self.group) / len(self.group)) + 2

        command_needed : list[int] = []

        # point3d = Point(x=self.target.x, y=self.target.y, z=ai.get_terrain_height(self.target))
        # ai.client.debug_sphere_out(point3d, radius_needed, Point2((0, 255, 0)))

        for unit in self.group:
            if not self.duplicate_or_similar_order(unit, self.target, AbilityId.MOVE, radius_needed * radius_needed):
                command_needed.append(unit.tag)

        ai.give_same_action(AbilityId.MOVE, command_needed, self.target)
        return len(command_needed) > 0

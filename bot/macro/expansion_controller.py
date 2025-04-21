# expansion_controller.py

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId as UnitId

if TYPE_CHECKING:
    from ares import AresBot

from ares.behaviors.macro.macro_behavior import MacroBehavior
from ares.managers.manager_mediator import ManagerMediator

@dataclass
class ExpansionController(MacroBehavior):
    """Manage Expanding on the map. Similar to the default but contains several extra enhancements such as pylon
    placement near the base for protoss.

    """

    def execute(self, ai: "AresBot", config: dict, mediator: ManagerMediator) -> bool:
        """Execute the Expand macro behavior."""

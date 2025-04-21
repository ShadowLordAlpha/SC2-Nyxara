# townhall_pylon_controller.py

from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger
from sc2.data import Race
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.position import Point2

if TYPE_CHECKING:
    from ares import AresBot

from cython_extensions import cy_unit_pending

from ares.behaviors.macro.build_structure import BuildStructure
from ares.behaviors.macro.macro_behavior import MacroBehavior
from ares.managers.manager_mediator import ManagerMediator

@dataclass
class TownhallPylonController(MacroBehavior):
    """Build a pylon next to each townhall."""

    def execute(self, ai: "AresBot", config: dict, mediator: ManagerMediator) -> bool:
        """Execute the TownhallPylonController macro behavior."""


        # For every townhall
        townhalls = ai.townhalls
        for townhall in townhalls:
            if townhall.race == Race.Protoss:
                # See if we have a pylong close by
                pylon_nearby = ai.structures.filter(lambda u: u.type_id == UnitID.PYLON and u.distance_to(townhall) < 15)
                # If we don't have one then build one
                if not pylon_nearby and not ai.structure_pending(UnitID.PYLON):
                    if ai.can_afford(UnitID.PYLON):
                        # Build the pylon
                        logger.info(f"Building UnitTypeId.PYLON at {townhall.position}")
                        BuildStructure(townhall.position, UnitID.PYLON, closest_to=townhall.position).execute(ai, config, mediator)
                    return True

        return False
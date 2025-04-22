# combat_harass_manager.py
"""
Handle controlling our harassing units
"""
from enum import Enum
from itertools import cycle
from typing import TYPE_CHECKING, Dict, Set

from loguru import logger

from ares import ManagerMediator
from ares.consts import UnitRole, UnitTreeQueryType
from cython_extensions.units_utils import cy_closest_to
from ares.managers.manager import Manager
from sc2.data import Race
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

if TYPE_CHECKING:
    from ares import AresBot

class HarassOrders(str, Enum):
    pass

class HarassSquad:
    order: HarassOrders
    forces: Units

#HARASS_COMPOSITION : dict[Race, set] = {
#    Race.Protoss: {
#        [{"type": UnitID.ADEPT, "count": 6, "min": 1}],
#        [{"type": UnitID.ORACLE, "count": 2, "min": 1}],
#        [{"type": UnitID.ZEALOT, "count": 8, "min": 4}],
#    },
#    Race.Terran: {},
#    Race.Zerg: {},
#}

class HarassManager(Manager):

    def __init__(self, ai: "AresBot", config: Dict, mediator: ManagerMediator):
        super().__init__(ai, config, mediator)

        self.squads : list[HarassSquad] = None

    async def update(self, iteration: int) -> None:
        # logger.info("HarassManager update")

        # List of all units assigned to the Harassing role
        forces: Units = self.ai.mediator.get_units_from_role(role=UnitRole.HARASSING)
        pass

    def _update_squad_units(self, forces: Units):
        """Update the units in the squad"""

        # Cleanup the squads
        for squad in self.squads:
            missing = squad.forces.tags_not_in(forces.tags)
            if missing:
                squad.forces.remove(missing)

        # Remove empty squads
        self.squads = [squad for squad in self.squads if squad.forces]

        # for any Force unit not already in a squad
        owned_tags : set[int]
        for squad in self.squads:
            owned_tags.union(squad.forces.tags)

        missing = forces.tags_not_in(owned_tags)

    def _process_squad(self, forces: Units) -> None:
        """Process a squad of harassing units"""
        pass

    def _find_harass_point(self, forces: Units) -> Point2:
        """Find a target point for harassing units to move to"""
        if self.ai.time > 180:  # If we are later than 3 minutes, see if there is another target for us to try
            pass

        return self.ai.enemy_start_locations[0]
# chrono_controller.py

from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId as UnitId
from sc2.ids.buff_id import BuffId

if TYPE_CHECKING:
    from ares import AresBot

from ares.behaviors.macro.macro_behavior import MacroBehavior
from ares.managers.manager_mediator import ManagerMediator

@dataclass
class ChronoController(MacroBehavior):
    """Manage the Chrono effect from a Nexus

    Attributes:
        reserve_energy: Energy to keep in reserve on each nexus
        Defaults to 0
        boost_constructing_structures: Whether to boost structures that are being constructed
        Defaults to False
        priority_list: Order of which structures to boost first
    """

    reserve_energy: int = 0
    boost_constructing_structures: bool = False
    priority_list = [
        # Research Buildings
        UnitId.FORGE,
        UnitId.CYBERNETICSCORE,
        UnitId.TWILIGHTCOUNCIL,
        UnitId.FLEETBEACON,
        UnitId.TEMPLARARCHIVE,
        UnitId.DARKSHRINE,

        UnitId.STARGATE,
        UnitId.ROBOTICSBAY,
        UnitId.NEXUS,
        UnitId.WARPGATE,
        UnitId.GATEWAY,

        # Any Other Structure we may want to chrono
        UnitId.SHIELDBATTERY,
        UnitId.PYLON,
        UnitId.PHOTONCANNON,
        UnitId.ASSIMILATORRICH,
        UnitId.ASSIMILATOR,
    ]

    def execute(self, ai: "AresBot", config: dict, mediator: ManagerMediator) -> bool:
        """Execute the Chrono macro behavior."""

        # Check each Nexus to see if we have enough energy
        for nexus in ai.ready_townhalls:
            if nexus.type_id == UnitId.NEXUS and nexus.energy >= 50 + self.reserve_energy:
                sorted_all_our_units = sorted(ai.structures, key=lambda u: self.priority_list.index(u.type_id))

                for unit in sorted_all_our_units:
                    if not unit.is_ready and self.boost_constructing_structures and not BuffId.CHRONOBOOSTENERGYCOST in unit.buffs:
                        nexus(AbilityId.EFFECT_CHRONOBOOSTENERGYCOST, unit)
                        return True
                    elif unit.is_ready and not unit.is_idle and unit.is_powered and not BuffId.CHRONOBOOSTENERGYCOST in unit.buffs:
                        nexus(AbilityId.EFFECT_CHRONOBOOSTENERGYCOST, unit)
                        return True

        return False

# burrow_decision.py`

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sc2.data import Race

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
class BurrowDecision(CombatIndividualBehavior):
    """
    Decides if we should burrow a unit or not

    Attributes
    ----------
    unit : Unit
        The unit to burrow
    """

    unit: Unit

    BURROW_AT_HEALTH_PERC: float = 0.3
    UNBURROW_AT_HEALTH_PERC: float = 0.9

    def execute(self, ai: "AresBot", config: dict, mediator: ManagerMediator) -> bool:
        # If we cannot burrow then there is no point in actually doing anything
        if not AbilityId.BURROWUP in self.unit.abilities and not AbilityId.BURROWDOWN in self.unit.abilities:
            return False

        type = self.unit.type_id

        # get near enemy ground
        # ares uses `KDTree` algorithm for faster distance queries
        # let's make use of that
        near_enemy_ground: Units = mediator.get_units_in_range(
            start_points=[self.unit.position],
            distances=14,
            query_tree=UnitTreeQueryType.AllEnemy,
        )[0]

        # Does the enemy in range that we know of have a detector
        has_detector : bool = len(near_enemy_ground.filter(lambda u: u.is_detector)) > 0

        # If we are a widdowmine and enemy is in sight range we should burrow now, This one doesn't care if there is a detector or not
        if type is UnitID.WIDOWMINE:
            if not self.unit.is_burrowed and len(near_enemy_ground) > 0:
                self.unit(AbilityId.BURROWDOWN)
                return True
            elif self.unit.is_burrowed and len(near_enemy_ground) == 0:
                self.unit(AbilityId.BURROWUP)
                return True

        # TODO: worker burrow is needed as well

        if self.unit.race == Race.Zerg:
            if self.unit.is_burrowed and self.unit.health_percentage > self.UNBURROW_AT_HEALTH_PERC and not has_detector:
                self.unit(AbilityId.BURROWUP)
                return True
            elif not self.unit.is_burrowed and self.unit.health_percentage <= self.BURROW_AT_HEALTH_PERC or has_detector:
                self.unit(AbilityId.BURROWDOWN)
                return True

        # No action was done
        return False

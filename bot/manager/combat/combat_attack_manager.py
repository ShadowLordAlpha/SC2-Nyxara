# combat_attack_manager.py

from itertools import cycle
from typing import TYPE_CHECKING, Dict, Set

import numpy as np
from loguru import logger

from ares import ManagerMediator
from ares.behaviors.combat import CombatManeuver
from ares.behaviors.combat.group import KeepGroupSafe, PathGroupToTarget, AMoveGroup, StutterGroupBack, \
    StutterGroupForward
from ares.behaviors.combat.individual import PathUnitToTarget, AMove, StutterUnitBack, KeepUnitSafe, ShootTargetInRange
from ares.consts import UnitRole, UnitTreeQueryType, ALL_STRUCTURES, EngagementResult

from cython_extensions.units_utils import cy_closest_to, cy_in_attack_range, cy_sorted_by_distance_to
from cython_extensions.combat_utils import cy_pick_enemy_target

from ares.managers.manager import Manager
from sc2.data import Race
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from bot.combat.burrow_decision import BurrowDecision
from bot.combat.group.group_up import GroupUp

COMMON_UNIT_IGNORE_TYPES: set[UnitID] = {
    UnitID.EGG,
    UnitID.LARVA,
}

class AttackManager(Manager):

    def should_attack(self, forces: Units, enemy: Units) -> bool:
        """Determine if we are currently attacking or should start our attack"""
        return (self.ai.build_order_runner.chosen_opening == "4GateRush" and self.ai.supply_army > 6) or self.ai.mediator.can_win_fight(own_units=forces, enemy_units=enemy, timing_adjust=False, good_positioning=False, workers_do_no_damage=True).value > EngagementResult.LOSS_MARGINAL.value or self.ai.supply_left <= 0 # If we are not going to lose badly then engage
        # return False

    @property
    def attack_target(self) -> Point2:
        """What is the general point we would like to attack"""

        # Its still early game, just head to the enemy spawn, no need for anything fancy
        if self.ai.time < 240.0:
            return self.ai.enemy_start_locations[0]
        elif self.ai.enemy_structures:
            distance_from = cy_sorted_by_distance_to(self.ai.enemy_structures, self.ai.enemy_start_locations[0])
            farthest = distance_from[len(distance_from) - 1]
            logger.info(f"Farthest structure is {farthest.name} at {farthest.position}")
            return farthest.position
        else:
            # cycle through expansion locations
            if self.ai.is_visible(self.ai.current_base_target):
                self.ai.current_base_target = next(self.ai.expansions_generator)

            return self.ai.current_base_target


    async def update(self, iteration: int) -> None:

        # using role system to separate our fighting forces from other units
        # https://aressc2.github.io/ares-sc2/api_reference/manager_mediator.html#ares.managers.manager_mediator.ManagerMediator.get_units_from_role
        # see `self.on_unit_created` where we originally assigned units ATTACKING role
        forces: Units = self.ai.mediator.get_units_from_role(role=UnitRole.ATTACKING)
        if not forces:
            return

        known_enemy = self.ai.mediator.get_cached_enemy_army()

        group_location = self.manager_mediator.get_own_nat

        # Group attack stuff
        attacking_group_maneuver: CombatManeuver = CombatManeuver()

        # get a ground grid to path on, this already contains enemy influence
        grid: np.ndarray = self.ai.mediator.get_ground_grid

        # make a single call to self.attack_target property
        # otherwise it keep calculating for every unit
        target: Point2 = self.attack_target
        close_to = self.ai.mediator.get_cached_enemy_army().in_distance_between(target, 0, 20)



        if self.should_attack(forces, close_to):

            # attacking_group_maneuver.add(StutterGroupForward(forces, {u.tag for u in forces}, forces.center, target, close_to))
            attacking_group_maneuver.add(AMoveGroup(forces, {u.tag for u in forces}, target))
        else:
            attacking_group_maneuver.add(StutterGroupBack(forces, {u.tag for u in forces}, forces.center, group_location, grid))
            attacking_group_maneuver.add(GroupUp(forces, group_location.towards(target, 5)))

        # DON'T FORGET TO REGISTER OUR COMBAT MANEUVER!!
        self.ai.register_behavior(attacking_group_maneuver)

        # make a fast batch distance query to enemy units for all our units
        # key: unit tag, value: units in range of that unit tag
        # https://aressc2.github.io/ares-sc2/api_reference/manager_mediator.html#ares.managers.manager_mediator.ManagerMediator.get_units_in_range
        # as zerg we will only interact with ground enemy, else we should get all enemy
        # query_type: UnitTreeQueryType = UnitTreeQueryType.AllEnemy
        #
        #
        #
        # near_enemy: dict[int, Units] = self.ai.mediator.get_units_in_range(
        #     start_points=forces,
        #     distances=15,
        #     query_tree=query_type,
        #     return_as_dict=True,
        # )
        #
        #
        #
        #
        #
        # # use `ares-sc2` combat maneuver system
        # # https://aressc2.github.io/ares-sc2/api_reference/behaviors/combat_behaviors.html
        # for unit in forces:
        #     """
        #     Set up a new CombatManeuver, idea here is to orchestrate your combat
        #     by stacking behaviors in order of priority. If a behavior executes
        #     then all other behaviors will be ignored for this step.
        #     """
        #
        #     # set up a new CombatManeuver for our unit, we register this a bit later using:
        #     # self.register_behavior(attacking_maneuver)
        #     # but we add behaviors first
        #     attacking_maneuver: CombatManeuver = CombatManeuver()
        #
        #     # we already calculated close enemies, use unit tag to retrieve them
        #     all_close: Units = near_enemy[unit.tag].filter(
        #         lambda u: not u.is_memory and u.type_id not in COMMON_UNIT_IGNORE_TYPES
        #     )
        #     # separate enemy units from enemy structures
        #     only_enemy_units: Units = all_close.filter(
        #         lambda u: u.type_id not in ALL_STRUCTURES
        #     )
        #
        #     # TODO: Dodge AOE attacks
        #     attacking_maneuver.add(BurrowDecision(unit))  # Burrow Units
        #
        #     # enemy around, engagement control
        #     if all_close:
        #         # cython version of `cy_in_attack_range` is approximately 4
        #         # times speedup vs burnysc2's `all_close.in_attack_range_of`
        #
        #         # idea here is to attack anything in range if weapon is ready
        #         # check for enemy units first
        #         if in_attack_range := cy_in_attack_range(unit, only_enemy_units):
        #             # `ShootTargetInRange` will check weapon is ready
        #             # otherwise it will not execute
        #             attacking_maneuver.add(
        #                 ShootTargetInRange(unit=unit, targets=in_attack_range)
        #             )
        #         # then enemy structures
        #         elif in_attack_range := cy_in_attack_range(unit, all_close):
        #             attacking_maneuver.add(
        #                 ShootTargetInRange(unit=unit, targets=in_attack_range)
        #             )
        #
        #         enemy_target: Unit = cy_pick_enemy_target(all_close)
        #
        #         # low shield, keep protoss units safe
        #         if self.ai.race == Race.Protoss and unit.shield_percentage < 0.3:
        #             attacking_maneuver.add(KeepUnitSafe(unit=unit, grid=grid))
        #
        #         else:
        #             attacking_maneuver.add(
        #                 StutterUnitBack(unit=unit, target=enemy_target, grid=grid)
        #             )
        #
        #     # no enemy around, path to the attack target
        #     else:
        #         attacking_maneuver.add(
        #             PathUnitToTarget(unit=unit, grid=grid, target=target)
        #         )
        #         attacking_maneuver.add(AMove(unit=unit, target=target))
        #
        #     # DON'T FORGET TO REGISTER OUR COMBAT MANEUVER!!
        #     self.ai.register_behavior(attacking_maneuver)

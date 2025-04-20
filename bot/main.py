"""
---------------------------
Ares-sc2 Random Example Bot
---------------------------

All the logic is encapsulated within this single file to enhance clarity.
For more sophisticated projects, additional consideration in terms of
software engineering principles may be necessary.

"""
from itertools import cycle
from typing import Optional

import numpy as np
from ares import AresBot
from ares.behaviors.combat import CombatManeuver
from ares.behaviors.combat.individual import (
    AMove,
    KeepUnitSafe,
    PathUnitToTarget,
    ShootTargetInRange,
    StutterUnitBack,
    UseAbility,
)
from ares.behaviors.macro import (
    AutoSupply,
    BuildWorkers,
    GasBuildingController,
    MacroPlan,
    ProductionController,
    SpawnController,
    UpgradeController,
)
from ares.behaviors.macro import Mining, BuildStructure, ExpansionController
from ares.consts import ALL_STRUCTURES, WORKER_TYPES, ALL_WORKER_TYPES, UnitRole, UnitTreeQueryType
from cython_extensions import cy_closest_to, cy_in_attack_range, cy_pick_enemy_target
from sc2.data import Race
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.ids.upgrade_id import UpgradeId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from bot.burrow_decision import BurrowDecision
from bot.macro.chrono_controller import ChronoController

# this will be used for ares SpawnController behavior
ARMY_COMPS: dict[Race, dict] = {
    Race.Protoss: {
        UnitID.STALKER: {"proportion": 0.7, "priority": 1},
        UnitID.DARKTEMPLAR: {"proportion": 0.2, "priority": 0},
        UnitID.ZEALOT: {"proportion": 0.1, "priority": 1},
    },
    Race.Terran: {
        UnitID.MARINE: {"proportion": 1.0, "priority": 0},
    },
    Race.Zerg: {
        UnitID.ROACH: {"proportion": 1.0, "priority": 0},
    },
    # Example if using more than one unit
    # proportion's add up to 1.0 with 0 being the highest priority and 10 lowest
    # Race.Zerg: {
    #     UnitID.HYDRALISK: {"proportion": 0.15, "priority": 0},
    #     UnitID.ROACH: {"proportion": 0.8, "priority": 1},
    #     UnitID.ZERGLING: {"proportion": 0.05, "priority": 2},
    # },
}

COMMON_UNIT_IGNORE_TYPES: set[UnitID] = {
    UnitID.EGG,
    UnitID.LARVA,
    UnitID.CREEPTUMORBURROWED,
    UnitID.CREEPTUMORQUEEN,
    UnitID.CREEPTUMOR,
    UnitID.MULE,
}

DESIRED_UPGRADES: dict[Race, list[UpgradeId]] = {
    Race.Protoss: {
        UpgradeId.WARPGATERESEARCH,
        UpgradeId.CHARGE,
        UpgradeId.BLINKTECH,
        UpgradeId.DARKTEMPLARBLINKUPGRADE,
        UpgradeId.PROTOSSSHIELDSLEVEL1,
        UpgradeId.PROTOSSGROUNDWEAPONSLEVEL1,
        UpgradeId.PROTOSSGROUNDARMORSLEVEL1,
        UpgradeId.PROTOSSSHIELDSLEVEL2,
        UpgradeId.PROTOSSSHIELDSLEVEL3,
        UpgradeId.PROTOSSGROUNDWEAPONSLEVEL2,
        UpgradeId.PROTOSSGROUNDWEAPONSLEVEL3,
        UpgradeId.PROTOSSGROUNDARMORSLEVEL2,
        UpgradeId.PROTOSSGROUNDARMORSLEVEL3,
    },
    Race.Terran: {

    },
    Race.Zerg: {

    },
}


class MyBot(AresBot):
    expansions_generator: cycle
    current_base_target: Point2
    _begin_attack_at_supply: float
    BURROW_AT_HEALTH_PERC: float = 0.3
    UNBURROW_AT_HEALTH_PERC: float = 0.9

    def __init__(self, game_step_override: Optional[int] = None):
        """Initiate custom bot

        Parameters
        ----------
        game_step_override :
            If provided, set the game_step to this value regardless of how it was
            specified elsewhere
        """
        super().__init__(game_step_override)

        self._commenced_attack: bool = False

    @property
    def attack_target(self) -> Point2:
        if self.enemy_structures:
            # using a faster cython alternative here from cython extensions library
            # this is installed for ares users by default
            # see docs here for all available functions
            # https://aressc2.github.io/cython-extensions-sc2/
            return cy_closest_to(self.start_location, self.enemy_structures).position
        # not seen anything in early game, just head to enemy spawn
        elif self.time < 240.0:
            return self.enemy_start_locations[0]
        # else search the map
        else:
            # cycle through expansion locations
            if self.is_visible(self.current_base_target):
                self.current_base_target = next(self.expansions_generator)

            return self.current_base_target

    async def on_start(self) -> None:
        """
        Can use burnysc2 hooks as usual, just add a call to the
        parent method before your own logic.
        """
        await super(MyBot, self).on_start()

        self.current_base_target = self.enemy_start_locations[0]
        self.expansions_generator = cycle(
            [pos for pos in self.expansion_locations_list]
        )
        self._begin_attack_at_supply = 3.0 if self.race == Race.Terran else 6.0

    async def on_step(self, iteration: int) -> None:
        await super(MyBot, self).on_step(iteration)

        self._macro()

        # using role system to separate our fighting forces from other units
        # https://aressc2.github.io/ares-sc2/api_reference/manager_mediator.html#ares.managers.manager_mediator.ManagerMediator.get_units_from_role
        # see `self.on_unit_created` where we originally assigned units ATTACKING role
        forces: Units = self.mediator.get_units_from_role(role=UnitRole.ATTACKING)

        if self._commenced_attack:
            self._micro(forces)

        elif self.get_total_supply(forces) >= self._begin_attack_at_supply:
            self._commenced_attack = True

    async def on_unit_created(self, unit: Unit) -> None:
        """
        Can use burnysc2 hooks as usual, just add a call to the
        parent method before your own logic.
        """
        await super(MyBot, self).on_unit_created(unit)

        # Don't assign Workers or Structures to ATTACKING role
        if unit.type_id in ALL_STRUCTURES or unit.type_id in ALL_WORKER_TYPES or unit.type_id in { UnitID.QUEEN, UnitID.OVERLORD, }:
            return

        # assign our forces ATTACKING by default
        # here we are making a request to an ares manager via the mediator
        # See https://aressc2.github.io/ares-sc2/api_reference/manager_mediator.html
        self.mediator.assign_role(tag=unit.tag, role=UnitRole.ATTACKING)

    def _macro(self) -> None:
        self.build_location = self.start_location
        if self.mediator.is_position_safe(position=self.start_location, grid=self.mediator.get_ground_grid):
            self.build_location = self.mediator.find_closest_safe_spot(from_pos=self.start_location, grid=self.mediator.get_ground_grid, radius=50)

                    # ares-sc2 Mining behavior
        # https://aressc2.github.io/ares-sc2/api_reference/behaviors/macro_behaviors.html#ares.behaviors.macro.mining.Mining
        self.register_behavior(Mining())

        # set up a simple macro plan, this could be extended if making a full macro bot, see docs here:
        # https://aressc2.github.io/ares-sc2/tutorials/managing_production.html#setting-up-a-macroplan
        macro_plan: MacroPlan = MacroPlan()
        macro_plan.add(ChronoController())

        if self.build_order_runner.build_completed:
            macro_plan.add(AutoSupply(base_location=self.build_location))
            macro_plan.add(BuildWorkers(to_count=min(80, len(self.townhalls) * 21 + 3))) # TODO: check the mineral fields we have and * 2 that instead of using townhalls
            macro_plan.add(GasBuildingController(to_count=len(self.townhalls) * 2))
            macro_plan.add(ExpansionController(to_count=len(self.expansion_locations_list), max_pending=2))
            macro_plan.add(UpgradeController(DESIRED_UPGRADES[self.race], self.build_location))

            macro_plan.add(SpawnController(ARMY_COMPS[self.race], freeflow_mode=True))

            if len(self.townhalls) > 3:
                macro_plan.add(ProductionController(ARMY_COMPS[self.race], self.build_location, (400, 200)))

        self.register_behavior(macro_plan)

    def _micro(self, forces: Units) -> None:
        # make a fast batch distance query to enemy units for all our units
        # key: unit tag, value: units in range of that unit tag
        # https://aressc2.github.io/ares-sc2/api_reference/manager_mediator.html#ares.managers.manager_mediator.ManagerMediator.get_units_in_range
        # as zerg we will only interact with ground enemy, else we should get all enemy
        query_type: UnitTreeQueryType = (
            UnitTreeQueryType.EnemyGround
            if self.race == Race.Zerg
            else UnitTreeQueryType.AllEnemy
        )
        near_enemy: dict[int, Units] = self.mediator.get_units_in_range(
            start_points=forces,
            distances=15,
            query_tree=query_type,
            return_as_dict=True,
        )

        # get a ground grid to path on, this already contains enemy influence
        grid: np.ndarray = self.mediator.get_ground_grid

        # make a single call to self.attack_target property
        # otherwise it keep calculating for every unit
        target: Point2 = self.attack_target

        # use `ares-sc2` combat maneuver system
        # https://aressc2.github.io/ares-sc2/api_reference/behaviors/combat_behaviors.html
        for unit in forces:
            """
            Set up a new CombatManeuver, idea here is to orchestrate your micro
            by stacking behaviors in order of priority. If a behavior executes
            then all other behaviors will be ignored for this step.
            """

            # set up a new CombatManeuver for our unit, we register this a bit later using:
            # self.register_behavior(attacking_maneuver)
            # but we add behaviors first
            attacking_maneuver: CombatManeuver = CombatManeuver()

            # we already calculated close enemies, use unit tag to retrieve them
            all_close: Units = near_enemy[unit.tag].filter(
                lambda u: not u.is_memory and u.type_id not in COMMON_UNIT_IGNORE_TYPES
            )
            # separate enemy units from enemy structures
            only_enemy_units: Units = all_close.filter(
                lambda u: u.type_id not in ALL_STRUCTURES
            )


            # TODO: Dodge AOE attacks
            attacking_maneuver.add(BurrowDecision(unit)) # Burrow Units

            # enemy around, engagement control
            if all_close:
                # cython version of `cy_in_attack_range` is approximately 4
                # times speedup vs burnysc2's `all_close.in_attack_range_of`

                # idea here is to attack anything in range if weapon is ready
                # check for enemy units first
                if in_attack_range := cy_in_attack_range(unit, only_enemy_units):
                    # `ShootTargetInRange` will check weapon is ready
                    # otherwise it will not execute
                    attacking_maneuver.add(
                        ShootTargetInRange(unit=unit, targets=in_attack_range)
                    )
                # then enemy structures
                elif in_attack_range := cy_in_attack_range(unit, all_close):
                    attacking_maneuver.add(
                        ShootTargetInRange(unit=unit, targets=in_attack_range)
                    )

                enemy_target: Unit = cy_pick_enemy_target(all_close)

                # low shield, keep protoss units safe
                if self.race == Race.Protoss and unit.shield_percentage < 0.3:
                    attacking_maneuver.add(KeepUnitSafe(unit=unit, grid=grid))

                else:
                    attacking_maneuver.add(
                        StutterUnitBack(unit=unit, target=enemy_target, grid=grid)
                    )

            # no enemy around, path to the attack target
            else:
                attacking_maneuver.add(
                    PathUnitToTarget(unit=unit, grid=grid, target=target)
                )
                attacking_maneuver.add(AMove(unit=unit, target=target))

            # DON'T FORGET TO REGISTER OUR COMBAT MANEUVER!!
            self.register_behavior(attacking_maneuver)

    def _terran_specific_macro(self):
        # use mules
        oc_id: UnitID = UnitID.ORBITALCOMMAND
        structures_dict: dict[
            UnitID, list[Unit]
        ] = self.mediator.get_own_structures_dict
        for oc in [s for s in structures_dict[oc_id] if s.energy >= 50]:
            mfs: Units = self.mineral_field.closer_than(10, oc)
            if mfs:
                mf: Unit = max(mfs, key=lambda x: x.mineral_contents)
                oc(AbilityId.CALLDOWNMULE_CALLDOWNMULE, mf)

        # lower depots
        for depot in self.mediator.get_own_structures_dict[UnitID.SUPPLYDEPOT]:
            if depot.type_id == UnitID.SUPPLYDEPOT:
                depot(AbilityId.MORPH_SUPPLYDEPOT_LOWER)

    def _zerg_specific_macro(self) -> None:
        if (
            not self.already_pending_upgrade(UpgradeId.BURROW)
            and self.townhalls.idle
            and self.build_order_runner.build_completed
            and self.can_afford(UpgradeId.BURROW)
        ):
            self.research(UpgradeId.BURROW)

        for queen in self.mediator.get_own_army_dict[UnitID.QUEEN]:
            if queen.energy >= 25 and self.townhalls:
                queen(AbilityId.EFFECT_INJECTLARVA, self.townhalls[0])

    """
    Can use `python-sc2` hooks as usual, but make a call the inherited method in the superclass
    Examples:
    """
    # async def on_end(self, game_result: Result) -> None:
    #     await super(MyBot, self).on_end(game_result)
    #
    #     # custom on_end logic here ...
    #
    # async def on_building_construction_complete(self, unit: Unit) -> None:
    #     await super(MyBot, self).on_building_construction_complete(unit)
    #
    #     # custom on_building_construction_complete logic here ...
    #
    # async def on_unit_destroyed(self, unit_tag: int) -> None:
    #     await super(MyBot, self).on_unit_destroyed(unit_tag)
    #
    #     # custom on_unit_destroyed logic here ...
    #
    # async def on_unit_took_damage(self, unit: Unit, amount_damage_taken: float) -> None:
    #     await super(MyBot, self).on_unit_took_damage(unit, amount_damage_taken)
    #
    #     # custom on_unit_took_damage logic here ...
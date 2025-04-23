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

from ares import AresBot, ManagerMediator, Hub, BuildOrderRunner
from ares.behaviors.macro import (
    AutoSupply,
    BuildWorkers,
    GasBuildingController,
    MacroPlan,
    ProductionController,
    SpawnController,
    UpgradeController, RestorePower,
)
from ares.behaviors.macro import Mining, ExpansionController
from ares.consts import ALL_STRUCTURES, ALL_WORKER_TYPES, UnitRole
from sc2.data import Race
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.ids.upgrade_id import UpgradeId
from sc2.position import Point2
from sc2.unit import Unit

from bot.macro.protoss.chrono_controller import ChronoController
from bot.macro.protoss.townhall_pylon_controller import TownhallPylonController
from bot.manager.combat.combat_attack_manager import AttackManager
from bot.manager.combat.combat_harass_manager import HarassManager
from bot.manager.custom_build_order_runner import CustomBuildOrderRunner

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
        self.harass_manager = None

    def register_managers(self) -> None:
        """
        Override the default `register_managers` in Ares, so we can add our own managers.
        """
        manager_mediator = ManagerMediator()

        self.harass_manager = HarassManager(self, self.config, manager_mediator)
        attack_manager = AttackManager(self, self.config, manager_mediator)

        self.manager_hub = Hub(self, self.config, manager_mediator, additional_managers=[self.harass_manager, attack_manager])
        self.manager_hub.init_managers()

    async def on_start(self) -> None:
        """
        Can use burnysc2 hooks as usual, just add a call to the
        parent method before your own logic.
        """
        await super(MyBot, self).on_start()

        # Literally all this does is override the persistent worker setting
        self.build_order_runner: BuildOrderRunner = CustomBuildOrderRunner(
            self,
            self.manager_hub.data_manager.chosen_opening,
            self.config,
            self.manager_hub.manager_mediator,
        )

        if self.build_order_runner.chosen_opening == "4GateRush":
            ARMY_COMPS[Race.Protoss] = {UnitID.ZEALOT: {"proportion": 1, "priority": 0}}

        self.current_base_target = self.enemy_start_locations[0]
        self.expansions_generator = cycle(
            [pos for pos in self.expansion_locations_list]
        )
        self._begin_attack_at_supply = 3.0 if self.race == Race.Terran else 6.0

        await self.chat_send("tag:" + self.build_order_runner.chosen_opening, False)

    async def on_step(self, iteration: int) -> None:
        await super(MyBot, self).on_step(iteration)

        self._macro()

    async def on_unit_created(self, unit: Unit) -> None:
        """
        Can use burnysc2 hooks as usual, just add a call to the
        parent method before your own logic.
        """
        await super(MyBot, self).on_unit_created(unit)


        # Don't assign Workers or Structures to ATTACKING role
        if unit.type_id in ALL_STRUCTURES or unit.type_id in ALL_WORKER_TYPES:
            return

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
        macro_plan.add(RestorePower())

        # After 60 seconds we can assume we need Pylons at the bases we own
        if self.time > 120:
            macro_plan.add(TownhallPylonController())

        if self.build_order_runner.chosen_opening != "4GateRush" or self.time > 300:
            if self.build_order_runner.build_completed:
                macro_plan.add(AutoSupply(base_location=self.build_location))
                macro_plan.add(BuildWorkers(to_count=min(90, len(self.townhalls) * 21 + 3))) # TODO: check the mineral fields we have and * 2 that instead of using townhalls
                macro_plan.add(GasBuildingController(to_count=len(self.townhalls) * 2))
                macro_plan.add(ExpansionController(to_count=len(self.expansion_locations_list), max_pending=2))
                macro_plan.add(UpgradeController(DESIRED_UPGRADES[self.race], self.build_location))


                macro_plan.add(SpawnController(ARMY_COMPS[self.race], spawn_target=self.current_base_target))

                if len(self.townhalls) > 3:
                    macro_plan.add(ProductionController(ARMY_COMPS[self.race], self.build_location, (400, 200)))
        elif self.build_order_runner.build_completed:
            macro_plan.add(AutoSupply(base_location=self.build_location))
            macro_plan.add(BuildWorkers(to_count=min(90, len(self.townhalls) * 21 + 3)))  # TODO: check the mineral fields we have and * 2 that instead of using townhalls
            macro_plan.add(ExpansionController(to_count=len(self.expansion_locations_list), max_pending=2))
            macro_plan.add(SpawnController(ARMY_COMPS[self.race], spawn_target=self.current_base_target))
            macro_plan.add(ProductionController(ARMY_COMPS[self.race], self.build_location, (400, 200)))


        self.register_behavior(macro_plan)

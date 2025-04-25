# protoss_proxy_4_gate.py
"""
Proxy 4 gate opening for Protoss. This cheese normally either wins or dies but is a really good cheese to have
"""
import numpy as np
from cython_extensions import cy_sorted_by_distance_to, cy_pick_enemy_target, cy_in_attack_range
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from ares import UnitRole
from ares.behaviors.combat import CombatManeuver
from ares.behaviors.combat.group import AMoveGroup
from ares.behaviors.combat.individual import WorkerKiteBack, KeepUnitSafe, AttackTarget, ShootTargetInRange, AMove
from ares.behaviors.macro import MacroPlan, Mining, RestorePower, SpawnController, AutoSupply, BuildWorkers, \
    ProductionController, ExpansionController, GasBuildingController, UpgradeController
from ares.consts import ALL_WORKER_TYPES, UnitTreeQueryType, ALL_STRUCTURES
from ares.managers.manager import Manager

from loguru import logger
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.ids.upgrade_id import UpgradeId

from ares.managers.squad_manager import UnitSquad
from bot.combat.group.group_a_move import GroupAMove
from bot.macro.protoss.chrono_controller import ChronoController

ARMY_COMP : dict = {
    UnitID.ZEALOT: {"proportion": 1, "priority": 0},
}

DESIRED_UPGRADES : list[UpgradeId] = [
    UpgradeId.CHARGE,
    UpgradeId.PROTOSSGROUNDWEAPONSLEVEL1,
    UpgradeId.WARPGATERESEARCH,
    UpgradeId.PROTOSSSHIELDSLEVEL1,
    UpgradeId.PROTOSSGROUNDARMORSLEVEL1,
    UpgradeId.PROTOSSSHIELDSLEVEL2,
    UpgradeId.PROTOSSSHIELDSLEVEL3,
    UpgradeId.PROTOSSGROUNDWEAPONSLEVEL2,
    UpgradeId.PROTOSSGROUNDWEAPONSLEVEL3,
    UpgradeId.PROTOSSGROUNDARMORSLEVEL2,
    UpgradeId.PROTOSSGROUNDARMORSLEVEL3,
]

COMMON_UNIT_IGNORE_TYPES: set[UnitID] = {
    UnitID.EGG,
    UnitID.LARVA,
}

PRIORITY_ATTACK_ORDER : list[UnitID] = [
    UnitID.SPINECRAWLER,
    UnitID.SPINECRAWLERUPROOTED,
    UnitID.BUNKER,
    UnitID.PHOTONCANNON,
    UnitID.QUEEN,
]

class Proxy4GateManager(Manager):
    """
    Proxy 4 Gate Manager for Protoss. This manager ensures that we do roughly the correct actions and use the correct
    behaviors to maximize the cheese and not mess it up with more generic logic while still being able to use the same
    generic parts.

    TODO: We currently use Zealots for the proxy. We may be able to expand this to adepts as an alternative. Problem is
            that adepts are just worse than zealots except they have some range and shade stalkers may work but would
            be harder
    """

    start_proxy_attack : bool = False # Initial start, after this triggers it stays on
    worker_mineralline_defense_message : bool = False # We only want to send the tag once, so this is to keep track of that

    async def update(self, iteration: int) -> None:
        """
        
        """

        zealots = self.ai.units(UnitID.ZEALOT)
        squads: list[UnitSquad] = self.manager_mediator.get_squads(role=UnitRole.ATTACKING, squad_radius=9.0)

        if zealots.amount > 2 and not self.start_proxy_attack:
            await self.ai.chat_send(f"Tag:{self.ai.time_formatted}_BeginZealotAttack")
            self.start_proxy_attack = True

        # TODO: Check for enemy cheese that we may need to defend against like worker rush

        # Assign Units to their proper Job here if they are not assigned ??? TODO: maybe after?

        # If we need to reassign units then do it here

        # Calculate what we need for everything else now... basically make macro and combat decisions

        # Setup Combat Behaviors
        if squads:
            if self.start_proxy_attack:
                # attack the enemy area
                target = self.attack_target
            else:
                target = zealots.center

            for squad in squads:
                combat_plan: CombatManeuver = CombatManeuver()
                combat_plan.add(GroupAMove(squad.squad_units, target))
                self.ai.register_behavior(combat_plan)


        # if zealots:
        #     # get a ground grid to path on, this already contains enemy influence
        #     grid: np.ndarray = self.ai.mediator.get_ground_grid
        #
        #     near_enemy: dict[int, Units] = self.ai.mediator.get_units_in_range(
        #         start_points=zealots,
        #         distances=15,
        #         query_tree=UnitTreeQueryType.EnemyGround,
        #         return_as_dict=True,
        #     )
        #
        #     if self.start_proxy_attack:
        #         # attack the enemy area
        #         target = self.attack_target
        #     else:
        #         target = zealots.center
        #
        #     for zealot in zealots:
        #         combat_plan: CombatManeuver = CombatManeuver()
        #         if near_enemy and near_enemy[zealot.tag]:
        #             # we already calculated close enemies, use unit tag to retrieve them
        #             all_close: Units = near_enemy[zealot.tag].filter(
        #                 lambda u: not u.is_memory and u.type_id not in COMMON_UNIT_IGNORE_TYPES
        #             )
        #
        #             if all_close:
        #                 # separate enemy units from enemy structures, filter workers as well from here
        #                 only_enemy_units: Units = all_close.filter(
        #                     lambda u: u.type_id not in ALL_STRUCTURES and u.type_id not in ALL_WORKER_TYPES
        #                 )
        #
        #                 if zealot.is_attacking:
        #                     combat_plan.add(ShootTargetInRange(zealot, only_enemy_units, 3))
        #                 else:
        #                     combat_plan.add(ShootTargetInRange(zealot, only_enemy_units, 5))
        #                 combat_plan.add(ShootTargetInRange(zealot, all_close, 15))
        #
        #         combat_plan.add(AMove(zealot, target))
        #         self.ai.register_behavior(combat_plan)

        # Setup worker Defense
        await self._defend_mineral_line()

        # Setup Macro Behaviors
        macro_plan: MacroPlan = MacroPlan()
        macro_plan.add(RestorePower())
        macro_plan.add(SpawnController(ARMY_COMP, spawn_target=self.ai.enemy_start_locations[0])) # spawn the units as close to enemy as possible

        # logger.info(f"testing {self.ai.structures(UnitID.GATEWAY).ready.amount}")
        # Once we have a gateway we want to prioritize it and we can enable use of the chrono controller
        if self.ai.structures(UnitID.GATEWAY).ready.amount > 0 or self.start_proxy_attack:
            macro_plan.add(ChronoController())
            macro_plan.add(AutoSupply(base_location=self.ai.start_location))

        if (self.start_proxy_attack or self.ai.time > 150) and self.ai.minerals > 150:
            macro_plan.add(ExpansionController(to_count=len(self.ai.expansion_locations_list)))
            macro_plan.add(BuildWorkers(to_count=min(90, max(len(self.ai.townhalls) * 21 + 4, 30))))

        if (self.start_proxy_attack or self.ai.time > 240) and self.ai.time > 240 and self.ai.townhalls.amount > 1: # at 4 minutes we can start upgrades
            macro_plan.add(GasBuildingController(to_count=1))
            macro_plan.add(UpgradeController(DESIRED_UPGRADES, self.ai.start_location))
            macro_plan.add(ProductionController(ARMY_COMP, self.ai.start_location, (400, 0)))

        self.ai.register_behavior(Mining()) # Ya... setting this in the macro plan breaks everything...
        self.ai.register_behavior(macro_plan)

    async def _defend_mineral_line(self):
        """
        Check if we are being attacked in a mineral line, if so add the workers in that line to the defense and attack
        the enemy if we would likely win. This will also return the workers to idle after the attack
        """

        defending_workers : set[int] = set()
        townhalls = self.ai.townhalls.ready
        for townhall in townhalls:
            # Get the list of minerals close to the townhall
            mineral_fields = self.ai.mineral_field.closer_than(10, townhall)

            # Get the enemy units near the minerals
            enemy_units = self.ai.enemy_units.closer_than(10, mineral_fields.center)

            if enemy_units:
                # There are enemies near, get the boys and defend the walls
                workers = self.ai.workers.closer_than(10, mineral_fields.center)
                self.manager_mediator.batch_assign_role(tags=workers.tags, role=UnitRole.DEFENDING)
                defending_workers.update(workers.tags)

                for worker in workers:
                    if not self.worker_mineralline_defense_message:
                        await self.ai.chat_send(f"Tag:{self.ai.time_formatted}_WorkerMinerallineDefense")
                        self.worker_mineralline_defense_message = True
                    # TODO: better targeting, for now the first will work
                    self.ai.register_behavior(WorkerKiteBack(unit=worker, target=enemy_units[0]))

        current_defenders = self.ai.mediator.get_units_from_role(role=UnitRole.DEFENDING, unit_type=ALL_WORKER_TYPES)
        release_workers = current_defenders.tags.difference(defending_workers)
        if release_workers:
            self.manager_mediator.batch_assign_role(tags=release_workers, role=UnitRole.GATHERING)

    @property
    def attack_target(self) -> Point2:
        """What is the general point we would like to attack"""

        # Its still early game, just head to the enemy spawn, no need for anything fancy
        if self.ai.time < 240.0:
            return self.ai.enemy_start_locations[0]
        elif self.ai.enemy_structures:
            distance_from = cy_sorted_by_distance_to(self.ai.enemy_structures, self.ai.enemy_start_locations[0])
            farthest = distance_from[len(distance_from) - 1]
            return farthest.position
        else:
            # cycle through expansion locations
            if self.ai.is_visible(self.ai.current_base_target):
                self.ai.current_base_target = next(self.ai.expansions_generator)

            return self.ai.current_base_target

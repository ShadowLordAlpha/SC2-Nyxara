# protoss_proxy_4_gate.py
"""
Proxy 4 gate opening for Protoss. This cheese normally either wins or dies but is a really good cheese to have
"""
from ares.behaviors.combat import CombatManeuver
from ares.behaviors.macro import MacroPlan, Mining, RestorePower, SpawnController, AutoSupply, BuildWorkers, \
    ProductionController, ExpansionController, GasBuildingController, UpgradeController
from ares.managers.manager import Manager

from loguru import logger
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.ids.upgrade_id import UpgradeId

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

    async def update(self, iteration: int) -> None:
        """
        
        """

        if self.ai.units(UnitID.ZEALOT).amount > 3:
            self.start_proxy_attack = True

        # TODO: Check for enemy cheese that we may need to defend against like worker rush

        # Assign Units to their proper Job here if they are not assigned ??? TODO: maybe after?

        # If we need to reassign units then do it here

        # Calculate what we need for everything else now... basically make macro and combat decisions

        # Setup Combat Behaviors
        combat_plan: CombatManeuver = CombatManeuver()
        if self.start_proxy_attack:
            # attack the enemy area
            pass
        else:
            # Defend our own area
            pass

        self.ai.register_behavior(combat_plan)

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

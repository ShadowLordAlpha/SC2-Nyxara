from typing import TYPE_CHECKING, Optional, Union

from cython_extensions import cy_distance_to_squared, cy_towards
from cython_extensions.combat_utils import cy_attack_ready
from cython_extensions.units_utils import cy_closest_to, cy_in_attack_range
from sc2.constants import ALL_GAS
from sc2.data import Race
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.ids.upgrade_id import UpgradeId
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from ares.behaviors.macro import AutoSupply, SpawnController
from ares.build_runner.build_order_step import BuildOrderStep
from ares.managers.manager_mediator import ManagerMediator

if TYPE_CHECKING:
    from ares import AresBot

from loguru import logger
from sc2.ids.ability_id import AbilityId

from ares import BuildOrderRunner
from ares.build_runner.build_order_parser import BuildOrderParser
from ares.consts import (
    ADD_ONS,
    ALL_STRUCTURES,
    BUILDS,
    GAS_BUILDINGS,
    GATEWAY_UNITS,
    OPENING_BUILD_ORDER,
    TARGET,
    WORKER_TYPES,
    BuildOrderOptions,
    BuildOrderTargetOptions,
    UnitRole,
)
from ares.dicts.structure_to_building_size import STRUCTURE_TO_BUILDING_SIZE


class CustomBuildOrderRunner(BuildOrderRunner):
    """
    A class to run a build order for an AI.

    Attributes:
        ai: The AI that the build order is for.
        _chosen_opening: The name of the opening being used for the build order.
        config: The configuration dictionary for the AI.
        mediator: The ManagerMediator object used for communicating with managers.
        build_order: The build order list.
        build_step: The current build order step index.
        current_step_started: True if the current build order step has started,
            False otherwise.
        _opening_build_completed: True if the opening build is completed,
            False otherwise.

    Methods:
        run_build: Runs the build order.
        do_step: Runs a specific build order step.

    """

    async def do_step(self, step: BuildOrderStep) -> None:
        """
        Runs a specific build order step.

        Parameters
        ----------
        step : BuildOrderStep
            The build order step to run.
        """
        if (
            step.command in GATEWAY_UNITS
            and UpgradeId.WARPGATERESEARCH in self.ai.state.upgrades
            and [
                g
                for g in self.mediator.get_own_structures_dict[UnitID.GATEWAY]
                if g.is_ready and g.is_idle
            ]
        ):
            return

        start_at_supply: int = step.start_at_supply
        start_condition_triggered: bool = step.start_condition()
        # start condition is active for a structure? reduce the supply threshold
        # this allows a worker to be sent earlier
        if (
            self.ai.race == Race.Protoss
            and start_condition_triggered
            and step.command in ALL_STRUCTURES
            and step.command != UnitID.PYLON
        ):
            start_at_supply -= 1
        if (
            start_condition_triggered
            and not self.current_step_started
            and self.ai.supply_used >= start_at_supply
        ):
            command: UnitID = step.command
            if command in ADD_ONS:
                self.current_step_started = True
            elif command in ALL_STRUCTURES:
                # let the gas steal preventer handle this step
                if command in GAS_BUILDINGS and len(self._geyser_tag_to_probe_tag) > 0:
                    self.current_step_started = True
                    return

                persistent_workers: Units = self.mediator.get_units_from_role(
                    role=UnitRole.PERSISTENT_BUILDER
                )
                building_tracker: dict = self.mediator.get_building_tracker_dict
                persistent_worker_available: bool = False
                if self.persistent_worker:
                    for worker in persistent_workers:
                        if self.ai.race == Race.Protoss:
                            persistent_worker_available = True
                            break
                        if worker.tag in building_tracker:
                            target: Point2 = building_tracker[worker.tag][TARGET]
                            if [
                                s
                                for s in self.ai.structures
                                if cy_distance_to_squared(s.position, target) < 6
                                and s.build_progress > 0.95
                            ]:
                                persistent_worker_available = True
                if worker := self.mediator.select_worker(
                    target_position=self.current_build_position,
                    force_close=True,
                    select_persistent_builder=command != UnitID.REFINERY,
                    only_select_persistent_builder=persistent_worker_available,
                ):
                    if next_building_position := await self.get_position(
                        step.command, step.target
                    ):
                        self.current_build_position = next_building_position

                        if self.mediator.build_with_specific_worker(
                            worker=worker,
                            structure_type=command,
                            pos=self.current_build_position,
                            assign_role=worker.tag
                            in self.mediator.get_unit_role_dict[UnitRole.GATHERING],
                        ):
                            self.current_step_started = True

            elif isinstance(command, UnitID) and command not in ALL_STRUCTURES:
                army_comp: dict = {command: {"proportion": 1.0, "priority": 0}}
                spawn_target: Point2 = self._get_target(step.target)
                did_spawn_action: bool = SpawnController(
                    army_comp, freeflow_mode=True, maximum=1, spawn_target=spawn_target
                ).execute(self.ai, self.config, self.mediator)
                if did_spawn_action:
                    if (
                        UpgradeId.WARPGATERESEARCH in self.ai.state.upgrades
                        and command in GATEWAY_UNITS
                    ):
                        # main.on_unit_created will set self.current_step_started = True
                        pass
                    else:
                        self.current_step_started = True

            elif isinstance(command, UpgradeId):
                self.current_step_started = True
                self.ai.research(command)

            elif command == AbilityId.EFFECT_CHRONOBOOST:
                if chrono_target := self.get_structure(step.target):
                    if available_nexuses := [
                        th
                        for th in self.ai.townhalls
                        if th.energy >= 50 and th.is_ready
                    ]:
                        available_nexuses[0](
                            AbilityId.EFFECT_CHRONOBOOSTENERGYCOST, chrono_target
                        )
                        self.current_step_started = True

            elif command == AbilityId.UPGRADETOORBITAL_ORBITALCOMMAND:
                if available_ccs := [
                    th
                    for th in self.ai.townhalls
                    if th.is_idle and th.is_ready and th.type_id == UnitID.COMMANDCENTER
                ]:
                    available_ccs[0](AbilityId.UPGRADETOORBITAL_ORBITALCOMMAND)
                    self.current_step_started = True

            elif command == BuildOrderOptions.WORKER_SCOUT:
                if worker := self.mediator.select_worker(
                    target_position=self.ai.start_location
                ):
                    worker.return_resource()
                    for target in step.target:
                        worker.move(target, queue=True)
                    self.mediator.assign_role(
                        tag=worker.tag, role=UnitRole.BUILD_RUNNER_SCOUT
                    )
                    self.current_step_started = True
            elif command == BuildOrderOptions.OVERLORD_SCOUT:
                unit_role_dict: dict[
                    UnitRole, set[int]
                ] = self.mediator.get_unit_role_dict
                if overlords := [
                    ol
                    for ol in self.mediator.get_own_army_dict[UnitID.OVERLORD]
                    if ol.tag not in unit_role_dict[UnitRole.BUILD_RUNNER_SCOUT]
                ]:
                    overlord: Unit = overlords[0]
                    for i, target in enumerate(step.target):
                        overlord.move(target, queue=i != 0)
                    self.mediator.assign_role(
                        tag=overlord.tag, role=UnitRole.BUILD_RUNNER_SCOUT
                    )
                    self.current_step_started = True

        if self.current_step_started:
            if not self.current_step_complete:
                self.current_step_complete = step.end_condition()
            # end condition hasn't yet activated
            if not self.current_step_complete:
                command: Union[UnitID, UpgradeId] = step.command
                # sometimes gas building didn't go through
                # due to conflict with gas steal
                if (
                    command in GAS_BUILDINGS
                    and len(self._geyser_tag_to_probe_tag) == 0
                    and self.mediator.get_building_counter[command] == 0
                ):
                    if worker := self.mediator.select_worker(
                        target_position=self.current_build_position, force_close=True
                    ):
                        if next_building_position := await self.get_position(
                            step.command, step.target
                        ):
                            self.current_build_position = next_building_position
                            self.mediator.build_with_specific_worker(
                                worker=worker,
                                structure_type=command,
                                pos=self.current_build_position,
                                assign_role=worker.tag
                                in self.mediator.get_unit_role_dict[UnitRole.GATHERING],
                            )
                elif command in ADD_ONS and self.ai.can_afford(command):
                    if base_structures := [
                        s
                        for s in self.ai.structures
                        if s.is_ready and s.is_idle and s.type_id == ADD_ONS[command]
                    ]:
                        base_structures[0].build(command)
                # should have already started upgraded when step started,
                # backup here just in case
                elif isinstance(command, UpgradeId):
                    self.ai.research(command)
                elif command == UnitID.ARCHON:
                    army_comp: dict = {command: {"proportion": 1.0, "priority": 0}}
                    SpawnController(army_comp, freeflow_mode=True, maximum=1).execute(
                        self.ai, self.config, self.mediator
                    )

            # end condition active, complete step
            else:
                time: str = self.ai.time_formatted
                logger.info(f"{self.ai.supply_used} {time} {step.command.name}")
                if self._temporary_build_step != -1:
                    self.build_order.remove(
                        self.build_order[self._temporary_build_step]
                    )
                    self._temporary_build_step = -1
                else:
                    self.build_step += 1

                self.current_step_started = False
                self.current_step_complete = False
                #if step.command == UnitID.PYLON:
                #    self.mediator.switch_roles(
                #        from_role=UnitRole.PERSISTENT_BUILDER,
                #        to_role=UnitRole.GATHERING,
                #    )

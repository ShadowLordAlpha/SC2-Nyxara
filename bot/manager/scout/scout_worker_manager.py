# scout_worker_manager.py
"""
Scout Worker Manager actually does the fine control of the units doing the scouting. This manager will scout the enemy
main base and then sit behind the minerals at the enemy natural until an expansion is seen OR the time hits X:XX
"""
from sc2.constants import WORKER_TYPES

from ares import UnitRole
from ares.managers.manager import Manager

class ScoutWorkerManager(Manager):

    async def update(self, iteration: int) -> None:

        # Get the workers that are assigned to Scout role
        worker_scouts = self.ai.mediator.get_units_from_role(role=UnitRole.SCOUTING, restrict_to=WORKER_TYPES)

        # If there are no worker scouts, return
        if not worker_scouts:
            return


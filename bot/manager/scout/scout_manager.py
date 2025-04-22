# scout_manager.py
"""
Scout Manager controls our scouting units to gather data
"""

from ares.managers.manager import Manager

class ScoutManager(Manager):

    shouldWorkerScout : bool = True

    def __init__(self, ai, config, mediator):
        super().__init__(ai, config, mediator)

    async def update(self, iteration: int) -> None:
        pass

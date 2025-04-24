# dynamic_controller.py
"""
Pass through manager to allow easily swapping to different managers
"""

from loguru import logger

from ares.managers.manager import Manager

class DynamicController(Manager):

    controller : Manager = None

    def set_controller(self, controller: Manager):
        """
        Set the controller to use, NOTE: this method is expected to run only after the on_start method has been
        triggered as we will also trigger the initialize method of the controller after setting
        """
        logger.info(f"{self.ai.time_formatted} Adding Dynamic controller: {controller.__class__.__name__}")
        self.controller = controller
        self.controller.initialise()

    def remove_controller(self):
        """
        Remove the current controller and reset it to None
        """
        logger.info(f"{self.ai.time_formatted} Removing Dynamic controller: {self.controller.__class__.__name__}")
        self.controller = None

    async def update(self, iteration: int) -> None:
        if self.controller is None:
            return

        await self.controller.update(iteration)

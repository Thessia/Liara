from enum import Enum


class CoreMode(Enum):
    up = 'up'  # respond to everyone (within checks)
    maintenance = 'maintenance'  # respond to owners
    down = 'down'  # respond to no one
    boot = 'boot'  # respond to no one until the next boot

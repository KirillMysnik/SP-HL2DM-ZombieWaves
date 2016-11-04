import json

from engines.server import global_vars
from entities.entity import Entity
from listeners import OnEntityDeleted, OnEntitySpawned, OnLevelInit
from mathlib import Vector
from paths import GAME_PATH, PLUGIN_DATA_PATH

from .info import info


MAPDATA_PATH = GAME_PATH / "mapdata" / "zombie_waves"

unloading = False
valid_npc_classnames = []
with open(PLUGIN_DATA_PATH / "zombie_waves" / "valid_npcs.res") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue

        valid_npc_classnames.append(line)


def dict_to_vector(dict_):
    return Vector(dict_['x'], dict_['y'], dict_['z'])


class ZombieSpawn:
    def __init__(self, dict_):
        self.origin = dict_to_vector(dict_['origin'])
        self.angles = dict_to_vector(dict_['angles'])
        self.classname = dict_['classname']


class ZombieSpawnStorage(list):
    def load_from_file(self):
        if not self.filepath.isfile():
            self.clear()
            return

        with open(self.filepath, 'r') as f:
            json_dict = json.load(f)

        for zombie_spawn_json in json_dict['zombie_spawns']:
            self.append(ZombieSpawn(zombie_spawn_json))

    @property
    def filepath(self):
        return MAPDATA_PATH / "{basename}.json".format(
            basename=global_vars.map_name)

zombie_spawn_storage = ZombieSpawnStorage()
zombie_entities = {}


def create_zombie_entities():
    for zombie_spawn in zombie_spawn_storage:
        entity = Entity.create(zombie_spawn.classname)
        entity.spawn()
        entity.teleport(zombie_spawn.origin, zombie_spawn.angles)

        zombie_entities[entity.index] = entity


def load():
    if global_vars.map_name:
        zombie_spawn_storage.load_from_file()
        create_zombie_entities()


def unload():
    global unloading
    unloading = True
    for entity in list(zombie_entities.values()):
        entity.remove()


@OnLevelInit
def listener_on_level_init(level_name):
    zombie_spawn_storage.load_from_file()
    create_zombie_entities()


@OnEntityDeleted
def listener_on_entity_deleted(base_entity):
    if unloading:
        return

    if not base_entity.is_networked():
        return

    zombie_entities.pop(base_entity.index, None)

    if not zombie_entities:
        create_zombie_entities()


@OnEntitySpawned
def listener_on_entity_spawned(base_entity):
    if base_entity.classname not in valid_npc_classnames:
        return

    entity = Entity(base_entity.index)
    entity.set_key_value_int('sleepstate', 0)
    entity.call_input('SetRelationship', 'player D_HT 99')

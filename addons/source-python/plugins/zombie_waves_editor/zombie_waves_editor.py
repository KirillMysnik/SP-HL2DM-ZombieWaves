from enum import IntEnum
import json

from colors import BLUE, ORANGE
from commands.typed import TypedClientCommand, TypedSayCommand
from effects import box
from engines.precache import Model
from engines.server import global_vars
from filters.recipients import RecipientFilter
from listeners import OnClientDisconnect, OnLevelInit
from listeners.tick import TickRepeat
from mathlib import Vector
from menus import SimpleMenu, SimpleOption, Text
from messages import SayText2
from paths import GAME_PATH, PLUGIN_DATA_PATH
from players.dictionary import PlayerDictionary

from advanced_ts import BaseLangStrings

from .info import info


TICK_REPEAT_INTERVAL = 0.1

EDITOR_STEP_UNITS = 1

INSPECT_LINE_COLOR = BLUE
INSPECT_LINE_MODEL = Model('sprites/laserbeam.vmt')
INSPECT_LINE_WIDTH = 2

HIGHLIGHT_LINE_COLOR = ORANGE
HIGHLIGHT_LINE_MODEL = Model('sprites/laserbeam.vmt')
HIGHLIGHT_LINE_WIDTH = 4

MAPDATA_PATH = GAME_PATH / "mapdata" / "zombie_waves"

BOX_HEIGHT = 80
BOX_WIDTH = 16

valid_npc_classnames = []
with open(PLUGIN_DATA_PATH / "zombie_waves" / "valid_npcs.res") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue

        valid_npc_classnames.append(line)

strings = BaseLangStrings(info.basename)

MSG_ZW_INSPECT_START = SayText2(strings['zw_inspect start'])
MSG_ZW_INSPECT_STOP = SayText2(strings['zw_inspect stop'])
MSG_ERR_INVALID_NPC = SayText2(strings['error invalid_npc'])


class HighlightChoice(IntEnum):
    HL_NEXT = 0
    HL_PREV = 1
    DELETE = 2


players = PlayerDictionary()
popups = {}


def round_vector(vector, step):
    vector.x = step * round(vector.x / step)
    vector.y = step * round(vector.y / step)
    vector.z = step * round(vector.z / step)


def vector_to_dict(vector):
    return {
        'x': vector.x,
        'y': vector.y,
        'z': vector.z
    }


def dict_to_vector(dict_):
    return Vector(dict_['x'], dict_['y'], dict_['z'])


def vector_to_str(vector):
    return "{x:.2f} {y:.2f} {z:.2f}".format(x=vector.x, y=vector.y, z=vector.z)


class ZombieSpawn:
    def __init__(self, *args):
        # From JSON-dict
        if isinstance(args[0], dict):
            dict_ = args[0]
            origin = dict_to_vector(dict_['origin'])
            angles = dict_to_vector(dict_['angles'])
            classname = dict_['classname']

        # From mins and maxs vectors
        else:
            origin, angles, classname = args

        self.origin = origin
        self.angles = angles
        self.classname = classname

        self._mins = self.origin + Vector(-BOX_WIDTH, -BOX_WIDTH, 0)
        self._maxs = self.origin + Vector(BOX_WIDTH, BOX_WIDTH, BOX_HEIGHT)

    def draw_inspect(self, recipients):
        box(
            recipients,
            self._mins,
            self._maxs,
            color=INSPECT_LINE_COLOR,
            life_time=TICK_REPEAT_INTERVAL,
            halo=INSPECT_LINE_MODEL,
            model=INSPECT_LINE_MODEL,
            start_width=INSPECT_LINE_WIDTH,
            end_width=INSPECT_LINE_WIDTH
        )

    def draw_highlight(self, recipients):
        box(
            recipients,
            self._mins,
            self._maxs,
            color=HIGHLIGHT_LINE_COLOR,
            life_time=TICK_REPEAT_INTERVAL,
            halo=HIGHLIGHT_LINE_MODEL,
            model=HIGHLIGHT_LINE_MODEL,
            start_width=HIGHLIGHT_LINE_WIDTH,
            end_width=HIGHLIGHT_LINE_WIDTH
        )

    def to_dict(self):
        dict_ = {
            'origin': vector_to_dict(self.origin),
            'angles': vector_to_dict(self.angles),
            'classname': self.classname
        }

        return dict_


class ZombieSpawnStorage(list):
    def save_to_file(self):
        json_dict = {
            'zombie_spawns': [],
        }
        for zombie_spawn in self:
            json_dict['zombie_spawns'].append(zombie_spawn.to_dict())

        with open(self.filepath, 'w') as f:
            json.dump(json_dict, f, indent=4)

    def load_from_file(self):
        self.clear()
        
        if not self.filepath.isfile():
            return

        with open(self.filepath, 'r') as f:
            json_dict = json.load(f)

        for zombie_spawn_json in json_dict['zombie_spawns']:
            self.append(ZombieSpawn(zombie_spawn_json))
            highlights.append_zombie_spawn()

    @property
    def filepath(self):
        return MAPDATA_PATH / "{basename}.json".format(
            basename=global_vars.map_name)

zombie_spawn_storage = ZombieSpawnStorage()


class Inspects(RecipientFilter):
    def __init__(self):
        super().__init__()
        self.remove_all_players()

    def tick(self):
        for zombie_spawn in zombie_spawn_storage:
            zombie_spawn.draw_inspect(self)

    def client_disconnect(self, index):
        self.remove_recipient(index)

inspects = Inspects()


class Highlights(list):
    def highlight_next(self, index):
        zombie_spawn_id = self.get_zombie_spawn_id_by_index(index)
        if zombie_spawn_id is None:
            if self:
                self[0].add_recipient(index)
                return zombie_spawn_storage[0]

            return None

        else:
            self[zombie_spawn_id].remove_recipient(index)

            zombie_spawn_id += 1
            if len(self) > zombie_spawn_id:
                self[zombie_spawn_id].add_recipient(index)
                return zombie_spawn_storage[zombie_spawn_id]

            else:
                return None

    def highlight_prev(self, index):
        zombie_spawn_id = self.get_zombie_spawn_id_by_index(index)
        if zombie_spawn_id is None:
            if self:
                self[-1].add_recipient(index)
                return zombie_spawn_storage[-1]

            return None

        else:
            self[zombie_spawn_id].remove_recipient(index)

            zombie_spawn_id -= 1
            if 0 <= zombie_spawn_id:
                self[zombie_spawn_id].add_recipient(index)
                return zombie_spawn_storage[zombie_spawn_id]

            else:
                return None

    def get_zombie_spawn_id_by_index(self, index):
        for zombie_spawn_id, recipients in enumerate(self):
            if index in recipients:
                return zombie_spawn_id

        return None

    def append_zombie_spawn(self):
        recipients = RecipientFilter()
        recipients.remove_all_players()
        self.append(recipients)

    def pop_zombie_spawn(self, zombie_spawn_id):
        self.pop(zombie_spawn_id)

    def tick(self):
        for zombie_spawn_id, recipients in enumerate(self):
            zombie_spawn_storage[zombie_spawn_id].draw_highlight(recipients)

    def client_disconnect(self, index):
        for recipients in self:
            recipients.remove_recipient(index)

highlights = Highlights()


def send_highlight_popup(index, zombie_spawn):
    if index in popups:
        popups[index].close(index)

    popup = popups[index] = SimpleMenu(
        select_callback=select_callback_highlight)

    popup.append(SimpleOption(
            choice_index=1,
            text=strings['popup highlight next_zombie_spawn'],
            value=HighlightChoice.HL_NEXT
    ))

    popup.append(SimpleOption(
        choice_index=2,
        text=strings['popup highlight prev_zombie_spawn'],
        value=HighlightChoice.HL_PREV
    ))

    if zombie_spawn is None:
        popup.append(
            Text(strings['popup highlight current_zombie_spawn none']))
    else:
        popup.append(
            Text(strings['popup highlight current_zombie_spawn'].tokenize(
                origin=vector_to_str(zombie_spawn.origin),
                angles=vector_to_str(zombie_spawn.angles),
                classname=zombie_spawn.classname
            ))
        )

        popup.append(SimpleOption(
            choice_index=3,
            text=strings['popup highlight delete'],
            value=HighlightChoice.DELETE
        ))

    popup.send(index)


def send_delete_popup(index):
    if index in popups:
        popups[index].close(index)

    popup = popups[index] = SimpleMenu(select_callback=select_callback_delete)
    popup.append(Text(strings['popup delete title']))
    popup.append(SimpleOption(
        choice_index=1,
        text=strings['popup delete no'],
        value=False
    ))
    popup.append(SimpleOption(
        choice_index=2,
        text=strings['popup delete yes'],
        value=True
    ))
    popup.send(index)


def select_callback_highlight(popup, index, option):
    if option.value == HighlightChoice.HL_NEXT:
        zombie_spawn = highlights.highlight_next(index)
        send_highlight_popup(index, zombie_spawn)
    elif option.value == HighlightChoice.HL_PREV:
        zombie_spawn = highlights.highlight_prev(index)
        send_highlight_popup(index, zombie_spawn)
    elif option.value == HighlightChoice.DELETE:
        send_delete_popup(index)


def select_callback_delete(popup, index, option):
    old_zombie_spawn_id = highlights.get_zombie_spawn_id_by_index(index)
    if old_zombie_spawn_id is None:
        return

    if option.value:
        zombie_spawn = highlights.highlight_prev(index)

        highlights.pop_zombie_spawn(old_zombie_spawn_id)
        zombie_spawn_storage.pop(old_zombie_spawn_id)

    else:
        zombie_spawn = zombie_spawn_storage[old_zombie_spawn_id]

    send_highlight_popup(index, zombie_spawn)


@OnClientDisconnect
def listener_on_client_disconnect(index):
    inspects.client_disconnect(index)
    highlights.client_disconnect(index)

    popups.pop(index, None)


@TickRepeat
def tick_repeat():
    inspects.tick()
    highlights.tick()

tick_repeat.start(TICK_REPEAT_INTERVAL, limit=0)


@OnLevelInit
def listener_on_level_init(level_name):
    popups.clear()
    players.clear()


@TypedClientCommand('zw_save_to_file', "zombie_waves_editor.create")
@TypedSayCommand('!zw_save_to_file', "zombie_waves_editor.create")
def typed_zw_save_to_file(command_info):
    zombie_spawn_storage.save_to_file()


@TypedClientCommand('zw_load_from_file', "zombie_waves_editor.create")
@TypedSayCommand('!zw_load_from_file', "zombie_waves_editor.create")
def typed_zw_load_from_file(command_info):
    zombie_spawn_storage.load_from_file()


@TypedClientCommand('zw_inspect', "zombie_waves_editor.inspect")
@TypedSayCommand('!zw_inspect', "zombie_waves_editor.inspect")
def typed_zw_inspect(command_info):
    if command_info.index in inspects:
        inspects.remove_recipient(command_info.index)
        MSG_ZW_INSPECT_STOP.send(command_info.index)
    else:
        inspects.add_recipient(command_info.index)
        MSG_ZW_INSPECT_START.send(command_info.index)


@TypedClientCommand('zw_highlight', "zombie_waves_editor.create")
@TypedSayCommand('!zw_highlight', "zombie_waves_editor.create")
def typed_zw_highlight(command_info):
    zombie_spawn_id = highlights.get_zombie_spawn_id_by_index(
        command_info.index)

    if zombie_spawn_id is None:
        send_highlight_popup(command_info.index, None)
    else:
        zombie_spawn = zombie_spawn_storage[zombie_spawn_id]
        send_highlight_popup(command_info.index, zombie_spawn)


@TypedClientCommand('zw_create', "zombie_waves_editor.create")
@TypedSayCommand('!zw_create', "zombie_waves_editor.create")
def typed_zw_create(command_info, classname:str):
    classname = classname.lower()

    if classname not in valid_npc_classnames:
        MSG_ERR_INVALID_NPC.send(command_info.index, classname=classname)
        return

    player = players[command_info.index]
    origin = player.origin
    angles = player.angles
    round_vector(origin, EDITOR_STEP_UNITS)

    zombie_spawn = ZombieSpawn(origin, angles, classname)
    zombie_spawn_storage.append(zombie_spawn)
    highlights.append_zombie_spawn()

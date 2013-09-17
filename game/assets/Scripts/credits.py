#
# Copyright 2013 Alex Fraser <alex@phatcore.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import bge

import bat.bats
import bat.containers
import bat.bmath
import bat.sound


_CREDIT_ITEMS = [
    'epilogue_saucebar',
    'epilogue_firefly',
    'epilogue_ant',
    'epilogue_saucebar',

    'None',

    ("A Game By", ["Alex Fraser"]),

    ("With excellent contributions from...", []),
    ("Story", ["Lara Micocki", "Lev Lafayette", "Jodie Fraser"]),

    ("Concept Art", ["Junki Wano"]),
    'concept_house',

    ("Modelling", ["Junki Wano", "Blender Foundation"]),
    'concept_truck',

#     ("Animation", []),
    ("Textures", ["Junki Wano"]),

    ("Music", ["Robert Leigh"]),
    'concept_worm',

    ("Programming", ["Mark Triggs", "Campbell Barton", "Ben Sturmfels",
            "Ashima Arts"]),
    'concept_lod',

    ("Sound Effects", ["Ben Sturmfels", "Ben Finney", "Leigh Raymond"]),
    ("And freesound.org users",
            ["3bagbrew", "FreqMan", "HerbertBoland", "Percy Duke", "klakmart", "aUREa",
            "qubodup", "thetruwu", "nsp", "kangaroovindaloo", "ERH", "Corsica_S",
            "batchku", "satrebor", "gherat", "ZeSoundResearchInc.", "CGEffex",
            "UncleSigmund", "dobroide"]),
    'concept_tree',

    ("Testing", ["Jodie Fraser", "Lachlan Kanaley", "Damien Elmes", "Mark Triggs", "Caley Finn"]),
    ("Made With", ["Blender", "Bullet", "The GIMP", "Inkscape", "Audacity", "Eclipse", "Git"]),
    'concept_catapult',

    'None',

    'logo_smidgin',
    ]

CREDITS = [item for item in _CREDIT_ITEMS
        if isinstance(item, tuple) and len(item[1]) > 0]

TRANSLATION_STEP = 0.004
# TRANSLATION_STEP = 0.02

def plate_generator(items):
    sce = bge.logic.getCurrentScene()
    for item in items:
        if isinstance(item, str):
            # Image (opaque/dumb object)
            yield bat.bats.add_and_mutate_object(sce, item)
        else:
            # Text object
            title, people = item
            plate_ob = bat.bats.add_and_mutate_object(sce, 'NamePlate')
            plate_ob.title = title
            plate_ob.people = '\n'.join(people)
            yield plate_ob

def flatzip(*iterables):
    iters = [iter(iterable) for iterable in iterables]
    while len(iters) > 0:
        print(iters)
        for i in iters[:]:
            try:
                yield(next(i))
            except StopIteration:
                iters.remove(i)

countdown = 60
current_plates = bat.containers.SafeList()
def update(c):
    global countdown
    for plate in current_plates:
        plate.update()

    if len(current_plates) <= 0:
        spawn_next_plate()
    else:
        if current_plates[-1].can_spawn_next():
            spawn_next_plate()

    if len(current_plates) <= 0:
        countdown -= 1
        if countdown <= 0:
            bge.logic.startGame('//Menu.blend')

plates = plate_generator(_CREDIT_ITEMS)
def spawn_next_plate():
    sce = bge.logic.getCurrentScene()
    spawn = sce.objects['PlateSpawn']
    try:
        plate = next(plates)
        plate.worldPosition = spawn.worldPosition
    except StopIteration:
        return
    current_plates.append(plate)

class Plate:
    def __init__(self, old_owner):
        pass

    def update(self):
        self.worldPosition.y += TRANSLATION_STEP
        if self.basepos > self.scene.objects['PlateKill'].worldPosition.y:
            current_plates[0].endObject()

    def can_spawn_next(self):
        return self.basepos > self.scene.objects['PlateMargin'].worldPosition.y

    @property
    def basepos(self):
        return self.worldPosition.y - self.height

class NamePlate(Plate, bat.bats.BX_GameObject, bge.types.KX_GameObject):
    def __init__(self, old_owner):
        self._title = bat.bats.mutate(self.children['Title'])
        self._people = bat.bats.mutate(self.children['People'])

    @property
    def title(self):
        #canvas = self.find_descendant([('role', 'title')])
        canvas = self._title
        return canvas['Content']
    @title.setter
    def title(self, value):
        canvas = self._title
        canvas['Content'] = value

    @property
    def people(self):
        #canvas = self.find_descendant([('role', 'people')])
        canvas = self._people
        return canvas['Content']
    @people.setter
    def people(self, value):
        canvas = self._people
        canvas['Content'] = value

    @property
    def height(self):
        if self.people != '':
            textob = self._people
        else:
            textob = self._title
        return -(textob.localPosition.y + textob.textbottom * textob.localScale.y)

class ImagePlate(Plate, bat.bats.BX_GameObject, bge.types.KX_GameObject):

    @property
    def height(self):
        if 'height' in self:
            return self['height']
        else:
            return 0

class LogoPlate(ImagePlate):
    SLOW_POINT = -0.3
    FADE_POINT = -0.05
    FADE_RATE = 0.005

    def update(self):
        # Move up at the same rate as other plates, but stop at the centre of
        # the screen. Slow down when approaching the centre. When very close,
        # fade to black.
        centrepos = self.worldPosition.y - (self.height * 0.5)
        step = bat.bmath.unlerp(0, LogoPlate.SLOW_POINT, centrepos)
        step = bat.bmath.clamp(0, 1, step)
        step *= TRANSLATION_STEP
        self.worldPosition.y += step
        if centrepos >= LogoPlate.FADE_POINT:
            # Fade to black. The sound should stop automatically by now, but
            # just in case, fade it out too.
            bat.sound.Jukebox().stop_all(fade_rate=LogoPlate.FADE_RATE)
            self.color.w -= LogoPlate.FADE_RATE
            if self.color.w <= 0.0001:
                self.endObject()

    def can_spawn_next(self):
        return False


def music(c):
    bat.sound.Jukebox().play_files('credits', c.owner, 1,
                '//Sound/Music/11-TheEnd_full.ogg',
                fade_in_rate=1, volume=0.6, loop=False)

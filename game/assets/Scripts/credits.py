'''
Created on 05/09/2013

@author: alex
'''

import bge

import bat.bats
import bat.containers
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

current_plates = bat.containers.SafeList()
def update(c):
    sce= bge.logic.getCurrentScene()
    for plate in current_plates:
        plate.worldPosition.y += TRANSLATION_STEP
    if len(current_plates) <= 0:
        spawn_next_plate()
    else:
        if current_plates[-1].basepos > sce.objects['PlateMargin'].worldPosition.y:
            spawn_next_plate()
        if current_plates[0].basepos > sce.objects['PlateKill'].worldPosition.y:
            current_plates[0].endObject()

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

class NamePlate(bat.bats.BX_GameObject, bge.types.KX_GameObject):
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
    def basepos(self):
        if self.people != '':
            textob = self._people
        else:
            textob = self._title
        height = textob.textbottom * textob.localScale.y
        base_pos = textob.worldPosition.y + height
        return base_pos

class ImagePlate(bat.bats.BX_GameObject, bge.types.KX_GameObject):
    def __init__(self, old_owner):
        pass

    @property
    def basepos(self):
        if 'height' in self:
            height = self['height']
        else:
            height = 1
        return self.worldPosition.y - height

def music(c):
    bat.sound.Jukebox().play_files('credits', c.owner, 1,
                '//Sound/Music/11-TheEnd_full.ogg',
                fade_in_rate=1, volume=0.6, loop=False)

'''
Created on 05/09/2013

@author: alex
'''

import bge

import bat.bats
import bat.containers
import bat.sound


CREDITS = [
    ("A Game By", ["Alex Fraser"]),
    ("Story", ["Lara Micocki", "Lev Lafayette", "Jodie Fraser"]),
    ("Concept Art", ["Junki Wano"]),
    ("Modelling", ["Junki Wano", "Blender Foundation"]),
#     ("Animation", []),
    ("Textures", ["Junki Wano"]),
    ("Music", ["Robert Leigh"]),
    ("Programming", ["Mark Triggs", "Campbell Barton", "Ben Sturmfels",
            "Ashima Arts"]),
    ("Sound Effects", ["Ben Sturmfels", "Ben Finney", "Leigh Raymond"]),
    ("And freesound.org users",
            ["3bagbrew", "FreqMan", "HerbertBoland", "Percy Duke", "klakmart", "aUREa",
            "qubodup", "thetruwu", "nsp", "kangaroovindaloo", "ERH", "Corsica_S",
            "batchku", "satrebor", "gherat", "ZeSoundResearchInc.", "CGEffex",
            "UncleSigmund", "dobroide"]),
    ("Testing", ["Jodie Fraser", "Lachlan Kanaley", "Damien Elmes", "Mark Triggs", "Caley Finn"]),
    ("Made With", ["Blender", "Bullet", "The GIMP", "Inkscape", "Audacity", "Eclipse", "Git"]),
    ]

ANNOTATIONS = [
    "With excellent contributions from...",
    ]

IMAGES = [
    'concept_snail',
    'concept_story',
    'concept_tree',
    'concept_worm',
    'concept_lod',
    'concept_catapult',
    'epilogue_saucebar',
    'epilogue_firefly',
    'epilogue_saucebar',
    'epilogue_firefly',
    ]

TRANSLATION_STEP = 0.005
# TRANSLATION_STEP = 0.05

def flatzip(*iterables):
    iters = [iter(iterable) for iterable in iterables]
    while len(iters) > 0:
        print(iters)
        for i in iters[:]:
            try:
                yield(next(i))
            except StopIteration:
                iters.remove(i)

def name_plate_generator():
    sce = bge.logic.getCurrentScene()
    for title, names in CREDITS:
        plate_ob = bat.bats.add_and_mutate_object(sce, 'NamePlate')
        plate_ob.title = title
        plate_ob.people = '\n'.join(names)
        yield plate_ob

def annotation_generator():
    sce = bge.logic.getCurrentScene()
    for annotation in ANNOTATIONS:
        plate_ob = bat.bats.add_and_mutate_object(sce, 'NamePlate')
        plate_ob.title = annotation
        plate_ob.people = ''
        yield plate_ob

def image_generator():
    sce = bge.logic.getCurrentScene()
    for image in IMAGES:
        plate_ob = bat.bats.add_and_mutate_object(sce, image)
        yield plate_ob

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

upcoming_plates = flatzip(name_plate_generator(), image_generator(), annotation_generator())
def spawn_next_plate():
    sce = bge.logic.getCurrentScene()
    spawn = sce.objects['PlateSpawn']
    try:
        plate = next(upcoming_plates)
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

import bpy

pattern = "bxt"

for o in bpy.data.objects:
    for c in o.game.controllers:
        if c.type != 'PYTHON':
            continue
        if c.module and pattern in c.module:
            print("%s / %s: %s" % (o.name, c.name, c.module))
        if c.text and pattern in c.text:
            print("%s / %s: %s" % (o.name, c.name, c.text))

import bpy

name = "frame"

for o in bpy.data.objects:
    if name in o.game.properties:
        print(o.name, ":", name, "=", o.game.properties[name].value)

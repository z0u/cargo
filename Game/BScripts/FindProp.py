import bpy

name = "Class"
newName = None

value = "Scripts.menu.Button"
newValue = "Scripts.gui.Button"

def get_path(ob):
    parents = []
    p = ob
    while p != None:
        parents.append(p)
        p = p.parent
    path = map(lambda x: x.name, reversed(parents))
    return "/" + "/".join(path)

for o in bpy.data.objects:
    if name is not None and name not in o.game.properties:
        continue
    prop = o.game.properties[name]

    if value is not None and value not in prop.value:
        continue

    print("%s/%s" % (get_path(o), o.name))
    if newName != None:
        print('\tRenaming: %s -> %s' % (name, newName))
        prop.name = newName

    if newValue != None:
        print('\tResetting: %s -> %s' % (value, newValue))
        prop.value = newValue
    else:
        print('\tValue = %s' % str(prop.value))

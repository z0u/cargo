import bpy

name = "parentName"
newName = "screenName"

def get_path(ob):
    parents = []
    p = ob
    while p != None:
        parents.append(p)
        p = p.parent
    path = map(lambda x: x.name, reversed(parents))
    return "/" + "/".join(path)

for o in bpy.data.objects:
    if name in o.game.properties:
        print("%s/%s" % (get_path(o), o.name))
        if newName != None:
            print('\tRenaming %s to %s' % (name, newName))
            o.game.properties[name].name = newName
        else:
            print('\tValue = %s' % str(o.game.properties[name].value))

import bpy

pattern = "Timer"
replace = None

def get_path(ob):
    parents = []
    p = ob
    while p != None:
        parents.append(p)
        p = p.parent
    path = map(lambda x: x.name, reversed(parents))
    return "/" + "/".join(path)

for o in bpy.data.objects:
    for c in o.game.controllers:
        if c.type != 'PYTHON':
            continue

        if c.module and pattern in c.module:
            print("%s/%s/%s" % (get_path(o), c.states, c.name))
            if replace != None:
                text = c.module.replace(pattern, replace)
                print("\tReplacing %s with %s" % (c.module, text))
                c.module = text
            else:
                print("\tFound", c.module)

        if c.text and pattern in c.text:
            print("%s/%s" % (get_path(o), c.states, c.name))
            if replace != None:
                text = c.text.replace(pattern, replace)
                print("\tReplacing %s with %s" % (c.text, text))
            else:
                print("\tFound", c.text)
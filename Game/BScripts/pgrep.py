import sys
import re
import bpy

#
# Modifies strings in Blender game properties.
#
# Run from within Blender, ("Run Script" from a text window), or from the
# command line like this:
#
# blender --factory-startup -b <FILE> -P pgrep.py -- <FIND_NAME> <REPLACE_NAME> <FIND_VALUE> <REPLACE_VALUE>
#

NAME = r"Class"
NEW_NAME = r"\0"

VALUE = r"Scripts.menu.Button"
NEW_VALUE = r"\0"

_dirty = False

def get_path(ob):
	parents = []
	p = ob
	while p != None:
		parents.append(p)
		p = p.parent
	path = map(lambda x: x.name, reversed(parents))
	return "/" + "/".join(path)

def find_or_replace(name, new_name, value, new_value):
	global _dirty
	for o in bpy.data.objects:
		for prop in o.game.properties:
			if re.search(name, prop.name) is None:
				continue
			if re.search(value, prop.value) is None:
				continue

			print("%s" % get_path(o))
			if new_name != r'\0':
				old_name = prop.name
				replaced_name = re.sub(name, new_name, prop.name)
				print('\tRenamed: %s -> %s' % (old_name, prop.name))
				if old_name != replaced_name:
					prop.name = replaced_name
					_dirty = True
			else:
				print('\tName: %s' % str(prop.name))

			if new_value != r'\0':
				old_value = prop.value
				replaced_value = re.sub(value, new_value, prop.value)
				print('\tChanged value: %s -> %s' % (old_value, prop.value))
				if old_value != replaced_value:
					prop.value = replaced_value
					_dirty = True
			else:
				print('\tValue: %s' % str(prop.value))

def run_from_commandline():
	global _dirty
	try:
		arg_separator = sys.argv.index('--')
	except ValueError:
		print("Error: missing arguments")
		return
	args = sys.argv[arg_separator + 1:]
	if len(args) != 4:
		print("Error: invalid arguments")
		return
	name = args[0]
	new_name = args[1]
	value = args[2]
	new_value = args[3]

	_dirty = False
	find_or_replace(name, new_name, value, new_value)
	if _dirty:
		print("Saving changes to", bpy.data.filepath)
		#bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)

if __name__ == "__main__":
	if bpy.app.background:
		run_from_commandline()
	else:
		find_or_replace(NAME, NEW_NAME, VALUE, NEW_VALUE)
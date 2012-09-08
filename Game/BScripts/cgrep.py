import sys
import re
import bpy

#
# Modifies strings in Blender controller logic bricks.
#
# Run from within Blender ("Run Script" from a text window), or from the
# command line like this:
#
# blender --factory-startup -b <FILE> -P cgrep.py -- <FIND_STR> <REPLACE_STR>
#

PATTERN = r'Shells.'
REPLACE = r'\0'

_dirty = False

def get_path(ob):
	parents = []
	p = ob
	while p != None:
		parents.append(p)
		p = p.parent
	path = map(lambda x: x.name, reversed(parents))
	return "/" + "/".join(path)

def find_or_replace(pattern, replace):
	global _dirty
	for o in bpy.data.objects:
		for c in o.game.controllers:
			if c.type != 'PYTHON':
				continue

			if c.module:
				if re.search(pattern, c.module) is None:
					continue
				print("%s#%s/%s" % (get_path(o), c.states, c.name))
				if replace != r'\0':
					old_value = c.module
					replaced_value = re.sub(pattern, replace, c.module)
					print("\tReplaced %s with %s" % (old_value, replaced_value))
					if old_value != replaced_value:
						c.module = replaced_value
						_dirty = True
				else:
					print("\tFound", c.module)

			if c.text:
				if re.search(pattern, c.text) is None:
					continue
				print("%s#%s/%s" % (get_path(o), c.states, c.name))
				if replace != r'\0':
					old_value = c.module
					replaced_value = re.sub(pattern, replace, c.text)
					print("\tReplaced %s with %s" % (old_value, replaced_value))
					if old_value != replaced_value:
						c.text = replaced_value
						_dirty = True
				else:
					print("\tFound", c.text)

def run_from_commandline():
	global _dirty
	try:
		arg_separator = sys.argv.index('--')
	except ValueError:
		print("Error: missing arguments")
		return
	args = sys.argv[arg_separator + 1:]
	if len(args) != 2:
		print("Error: invalid arguments")
		return

	_dirty = False
	find_or_replace(args[0], args[1])
	if _dirty:
		print("Saving changes to", bpy.data.filepath)
		#bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)

if __name__ == "__main__":
	if bpy.app.background:
		run_from_commandline()
	else:
		find_or_replace(PATTERN, REPLACE)

import sys
import re
import bpy

#
# Modifies strings in Blender library references
#
# Run from within Blender ("Run Script" from a text window), or from the
# command line like this:
#
# blender --factory-startup -b <FILE> -P lgrep.py -- <FIND_STR> <REPLACE_STR>
#

PATTERN = r'cargo/Game.'
REPLACE = r'\0'

_dirty = False

def find_or_replace(pattern, replace):
	global _dirty
	for l in bpy.data.libraries:
		if re.search(pattern, l.filepath) is None:
			continue
		if replace != r'\0':
			old_value = l.filepath
			replaced_value = re.sub(pattern, replace, l.filepath)
			print("\tReplaced %s with %s" % (old_value, replaced_value))
			if old_value != replaced_value:
				l.filepath = replaced_value
				_dirty = True
		else:
			print("\tFound", l.filepath)

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
		bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)

if __name__ == "__main__":
	if bpy.app.background:
		run_from_commandline()
	else:
		find_or_replace(PATTERN, REPLACE)

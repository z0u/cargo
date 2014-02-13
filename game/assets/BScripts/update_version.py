import sys

import bpy

try:
    arg_separator = sys.argv.index('--')
    output_path = sys.argv[arg_separator + 1]
except ValueError:
    print('Saving over current file')
    output_path = bpy.context.blend_data.filepath

bpy.ops.wm.save_mainfile(filepath=output_path)
bpy.ops.wm.quit_blender()

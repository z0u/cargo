import bpy

bpy.ops.wm.save_mainfile(filepath=bpy.context.blend_data.filepath)
bpy.ops.wm.quit_blender()


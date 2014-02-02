#
# Copyright 2014 Alex Fraser <alex@phatcore.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

'''
Saves Blender data as text. You can run this as an export addon, or
from the command line like this:

    blender -b input.blend -P ascblend.py -- output.txt

For help:

    blender -b -P ascblend.py -- -h
'''

import itertools
import time

import bpy
import bpy_extras


# Ignore some properties; these cause crashes or deep recursion, or
# are generally not useful.
IGNORE = {
    'bl_rna',
    'particle_edit',
    'rna_type',
    'type_info',
    'uv_texture_clone',
    'uv_layer_clone',
    }
IGNORE_IMAGE = {
    'pixels',
    }
IGNORE_OBDATA = {
    'vertices',
    'edges',
    'polygons',
    'tessfaces',
    'loops',
    # TODO: Should only exclude the .data children of these attributes.
    'uv_layers',
    'uv_textures',
    'uv_layer_stencil',
    'uv_texture_stencil',
    'vertex_colors',
    }
IGNORE_TEXTS = {
    'lines',
    }
IGNORE_ANIM = {
    'keyframe_points',
    }
IGNORE_UI = {
    'window_managers',
    'screens',
    'brushes',
    }

INDENT = "  "


def qualname(ob):
    return '%s.%s' % (ob.__class__.__module__, ob.__class__.__name__)


class Progress:

    INTERVAL = 1.0

    def __init__(self):
        self.last_update = 0

    def message(self, msg):
        t = time.time()
        if self.last_update < time.time() - Progress.INTERVAL:
            print(msg)
            self.last_update = t


class ObjectPrinter:

    is_leaf = False

    # Sort order for object properties. Repeated object references are not
    # printed in detail, so try to make the first reference come from an
    # immediate child of bpy.data. Basically this list should contain
    # names of collections that don't refer to other collections.
    ORDER = [
        'libraries',
        'texts',
        'actions',
        'images', 'fonts', 'sounds',
        'textures',
        'node_groups',
        'materials',
        'vertices', 'edges', 'polygons', 'tessfaces', 'uv_layers', 'uv_textures'
        'curves', 'meshes', 'lamps', 'cameras', 'metaballs', 'lattices', 'speakers',
        'particles',
        'objects', 'worlds',
        'groups',
        'scenes',
        'screens',
        'window_managers',
        ]

    def __init__(self, ignore):
        self.ignore = ignore

    def prettyprint(self, state, indent, path, name, ob):
        try:
            if ob is None:
                state.file.write("%s (None)\n" % path)
                return
            if ob in state.printed:
                state.file.write("%s (rpt)\n" % path)
                return
            state.printed.add(ob)
        except TypeError:
            return
        else:
            state.file.write("%s\n" % path)

        state.progress.message(path)

        attrs = dir(ob)
        attrs.sort(key=ObjectPrinter.propkey)
        leaves = []
        branches = []
        for attr in attrs:
            if attr.startswith('__'):
                continue
            if attr in self.ignore:
                continue
            try:
                child = getattr(ob, attr)
            except AttributeError as e:
                print("warning:", e)
                continue
            if state.dispatcher.is_leaf(child):
                leaves.append((attr, child))
            else:
                branches.append((attr, child))

        sub_indent = indent + INDENT
        for attr, child in itertools.chain(leaves, branches):
            childpath = "{p}.{col}".format(p=path, col=attr)
            state.dispatcher.dispatch(
                state, sub_indent, childpath, attr, child)

    @staticmethod
    def propkey(name):
        try:
            i = ObjectPrinter.ORDER.index(name)
        except ValueError:
            # If no match, place it after things that did match.
            i = len(ObjectPrinter.ORDER)
        return "_%3d%s" % (i, name)


class CollectionPrinter:

    is_leaf = False

    def __init__(self, named_keys=True):
        self.named_keys = named_keys

    def prettyprint(self, state, indent, path, name, col):
        if col in state.printed:
            return
        state.printed.add(col)

        state.progress.message(path)

        state.file.write("%s\n" % path)
        #state.file.write('%s__len__: %d\n' % (indent + INDENT, len(col)))
        for i, item in enumerate(col):
            if self.named_keys and hasattr(item, 'name'):
                index = "'%s'" % item.name
            else:
                index = "%d" % i
            childpath = "{p}[{i}]".format(p=path, i=index)
            #print(childpath)
            state.dispatcher.dispatch(
                state, indent + INDENT, childpath, index, item)


class TextPrinter:

    is_leaf = False

    def prettyprint(self, state, indent, path, name, text):
        if text in state.printed:
            return
        state.printed.add(text)

        for line in text.lines:
            state.file.write('{indent}{line}\n'.format(
                indent=indent, line=line.body))


class NullPrinter:

    is_leaf = True

    def prettyprint(self, state, indent, path, name, ob):
        return


class ReprPrinter:

    is_leaf = True

    def prettyprint(self, state, indent, path, name, ob):
        state.file.write('{indent}{name}: {value}\n'.format(
            indent=indent, name=name, value=repr(ob)))


class PrintDispatcher:

    def __init__(self, extra_ignore=None):
        self.handlers = {}

        # Generic objects
        ignore = IGNORE.copy()
        if extra_ignore is not None:
            ignore.update(extra_ignore)
        self.handlers['_default'] = ObjectPrinter(ignore)

        # Functions
        self.handlers['builtins.bpy_func'] = \
        self.handlers['builtins.method'] = \
            self.handlers['builtins.builtin_function_or_method'] = NullPrinter()

        # Mathutils types and primitives
        self.handlers['builtins.Vector'] = \
            self.handlers['builtins.Euler'] = \
            self.handlers['builtins.Quaternion'] = \
            self.handlers['builtins.Matrix'] = \
            self.handlers['builtins.str'] = \
            self.handlers['builtins.int'] = \
            self.handlers['builtins.float'] = \
            self.handlers['builtins.bool'] = ReprPrinter()

        # Collections
        self.handlers['builtins.bpy_prop_array'] = CollectionPrinter(
            named_keys=False)
        self.handlers['builtins.bpy_prop_collection'] = CollectionPrinter(
            named_keys=True)

        # Special handler for text
        self.handlers['bpy_types.Text'] = TextPrinter()

    def get_handler(self, ob):
        cls = qualname(ob)
        try:
            return self.handlers[cls]
        except KeyError:
            return self.handlers['_default']

    def dispatch(self, state, indent, path, name, ob):
        self.get_handler(ob).prettyprint(state, indent, path, name, ob)

    def is_leaf(self, ob):
        return self.get_handler(ob).is_leaf


class PrintState:

    def __init__(self, dispatcher, f):
        # Objects that have already been printed; when encountered again,
        # the reference but not the data will be printed again.
        self.printed = set()

        self.dispatcher = dispatcher
        self.file = f
        self.progress = Progress()


def export(filepath, include_ui, include_obdata, include_images, include_texts, include_anim, ignore):
    extra_ignore = set()
    extra_ignore.update(ignore)
    if not include_ui:
        extra_ignore.update(IGNORE_UI)
    if not include_obdata:
        extra_ignore.update(IGNORE_OBDATA)
    if not include_images:
        extra_ignore.update(IGNORE_IMAGE)
    if not include_texts:
        extra_ignore.update(IGNORE_TEXTS)
    if not include_anim:
        extra_ignore.update(IGNORE_ANIM)
    dispatcher = PrintDispatcher(extra_ignore)
    with open(filepath, 'w', encoding='utf-8') as f:
        state = PrintState(dispatcher, f)
        dispatcher.dispatch(state, '', 'bpy.data', 'data', bpy.data)


class TextExport(bpy.types.Operator, bpy_extras.io_utils.ExportHelper):
    """Export blend file data to plain text"""
    bl_idname = "export_scene.asc"
    bl_label = "Text (.txt)"

    # ExportHelper mixin class uses this
    filename_ext = ".txt"

    filter_glob = bpy.props.StringProperty(
            default="*.txt",
            options={'HIDDEN'},
            )

    # List of operator properties, the attributes will be assigned
    # to the class instance from the operator settings before calling.
    include_ui = bpy.props.BoolProperty(
            name="User Interface",
            description="Include UI configuration and tool settings (window_managers, screens, brushes)",
            default=False,
            )

    def execute(self, context):
        export(self.filepath, self.include_ui)
        return {'FINISHED'}


# Only needed if you want to add into a dynamic menu
def menu_func_export(self, context):
    self.layout.operator(TextExport.bl_idname)


def register():
    bpy.utils.register_class(TextExport)
    bpy.types.INFO_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_class(TextExport)
    bpy.types.INFO_MT_file_export.remove(menu_func_export)


def run_batch():
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Export .blend file to text.",
        usage="blender -b <infile> -P <this script> -- [args] <outfile>")
    parser.add_argument(
        '--ui', default=False,
        help="Include UI and tool settings.")
    parser.add_argument(
        '--obdata', default=False,
        help="Include object data.")
    parser.add_argument(
        '--images', default=False,
        help="Include pixel data.")
    parser.add_argument(
        '--texts', default=False,
        help="Include text and script contents.")
    parser.add_argument(
        '--anim', default=False,
        help="Include animation data (fcurves).")
    parser.add_argument(
        '--exclude', default='',
        help="Additional property names to ignore (comma-separated).")
    parser.add_argument(
        'filepath',
        help="The file to write to.")

    try:
        arg_sep = sys.argv.index('--')
    except ValueError:
        print("Error: missing arguments.")
        parser.print_help()
        sys.exit(1)

    args = sys.argv[arg_sep + 1:]
    print(args)
    args = parser.parse_args(args=args)
    ignore = args.exclude.split(',')
    export(args.filepath, args.ui, args.obdata, args.images, args.texts, args.anim, ignore)


if bpy.app.background:
    run_batch()
elif __name__ == "__main__":
    register()

import bpy
import bpy_extras


# Ignore some properties; these cause crashes or deep recursion, or
# are generally not useful.
IGNORE = {
    'bl_rna',
    'particle_edit',
    'rna_type',
    'type_info',
    }
IGNORE_UI = {
    'window_managers',
    'screens',
    'brushes'
    }

def qualname(ob):
    return '%s.%s' % (ob.__class__.__module__, ob.__class__.__name__)


class ObjectPrinter:

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

    def prettyprint(self, state, path, name, ob):
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

        attrs = dir(ob)
        attrs.sort(key=ObjectPrinter.propkey)
        for attr in attrs:
            if attr.startswith('__'):
                continue
            if attr in self.ignore:
                continue
            child = getattr(ob, attr)
            cls = qualname(child)
            childpath = "{p}.{col}".format(p=path, col=attr)
            state.dispatcher.dispatch(state, childpath, attr, child)

    @staticmethod
    def propkey(name):
        try:
            i = ObjectPrinter.ORDER.index(name)
        except ValueError:
            # If no match, place it after things that did match.
            i = len(ObjectPrinter.ORDER)
        return "_%3d%s" % (i, name)


class CollectionPrinter:

    def prettyprint(self, state, path, name, col):
        if col in state.printed:
            return
        state.printed.add(col)

        state.file.write("%s\n" % path)
        state.file.write('\t__len__: %d\n' % len(col))
        for i, item in enumerate(col):
            if hasattr(item, 'name'):
                index = "'%s'" % item.name
            else:
                index = "%d" % i
            childpath = "{p}[{i}]".format(p=path, i=index)
            #print(childpath)
            cls = qualname(item)
            state.dispatcher.dispatch(state, childpath, index, item)


class TextPrinter:

    def prettyprint(self, state, path, name, text):
        if text in state.printed:
            return
        state.printed.add(text)

        for line in text.lines:
            state.file.write('\t%s\n' % line.body)


class NullPrinter:

    def prettyprint(self, state, path, name, ob):
        return


class ReprPrinter:

    def prettyprint(self, state, path, name, ob):
        state.file.write('\t{name}: {value}\n'.format(name=name, value=repr(ob)))


class PrintDispatcher:

    def __init__(self, extra_ignore=None):
        self.handlers = {}
        ignore = IGNORE.copy()
        if extra_ignore is not None:
            ignore.update(extra_ignore)
        self.handlers['_default'] = ObjectPrinter(ignore)
        self.handlers['builtins.builtin_function_or_method'] = NullPrinter()
        self.handlers['builtins.str'] = \
            self.handlers['builtins.int'] = \
            self.handlers['builtins.float'] = \
            self.handlers['builtins.bool'] = ReprPrinter()
        self.handlers['builtins.bpy_prop_collection'] = CollectionPrinter()
        self.handlers['bpy_types.Text'] = TextPrinter()

    def dispatch(self, state, path, name, ob):
        cls = qualname(ob)
        if cls in self.handlers:
            self.handlers[cls].prettyprint(state, path, name, ob)
        else:
            self.handlers['_default'].prettyprint(state, path, name, ob)


class PrintState:
    def __init__(self, dispatcher, f):
        # Objects that have already been printed; when encountered again,
        # the reference but not the data will be printed again.
        self.printed = set()

        self.dispatcher = dispatcher
        self.file = f


def export(filepath, include_ui, ignore):
    if not include_ui:
        extra_ignore = IGNORE_UI
    else:
        extra_ignore = set()
    extra_ignore.update(ignore)
    dispatcher = PrintDispatcher(extra_ignore)
    with open(filepath, 'w', encoding='utf-8') as f:
        state = PrintState(dispatcher, f)
        dispatcher.dispatch(state, 'bpy.data', 'data', bpy.data)


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
    export(args.filepath, args.ui, ignore)


if bpy.app.background:
    run_batch()
elif __name__ == "__main__":
    register()

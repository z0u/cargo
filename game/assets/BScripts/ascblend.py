import bpy

# Maps classes to printers.
HANDLERS = {}

# Ignore some properties; these cause crashes or deep recursion, or
# are generally not useful.
IGNORE = {
    'bl_rna',
    'particle_edit',
    'rna_type',
    'type_info',
    }

# Objects that have already been printed; when encountered again,
# the reference but not the data will be printed again.
printed = set()


def qualname(ob):
    return '%s.%s' % (ob.__class__.__module__, ob.__class__.__name__)


def dispatch(path, name, ob):
    cls = qualname(ob)
    if cls in HANDLERS:
        HANDLERS[cls].prettyprint(path, name, ob)
    else:
        HANDLERS['_default'].prettyprint(path, name, ob)


class ObjectPrinter:

    # Sort order for object properties. Repeated object references are not
    # printed in detail, so try to make the first reference come from an
    # immediate child of bpy.data. Basically this list should contain
    # names of collections that don't refer to other collections.
    ORDER = [
        'libraries',
        'texts',
        'actions',
        'images', 'fonts',
        'textures',
        'node_groups',
        'materials',
        'curves', 'meshes', 'lamps', 'cameras', 'metaballs', 'lattices',
        'particles',
        'objects', 'worlds',
        'groups',
        'scenes',
        'screens',
        'window_managers',
        ]

    def prettyprint(self, path, name, ob):
        try:
            if ob is None:
                print("%s (None)" % path)
                return
            if ob in printed:
                print("%s (rpt)" % path)
                return
            printed.add(ob)
        except TypeError:
            return
        else:
            print(path)

        attrs = dir(ob)
        attrs.sort(key=ObjectPrinter.propkey)
        for attr in attrs:
            if attr.startswith('__'):
                continue
            if attr in IGNORE:
                continue
            child = getattr(ob, attr)
            cls = qualname(child)
            childpath = "{p}.{col}".format(p=path, col=attr)
            dispatch(childpath, attr, child)

    @staticmethod
    def propkey(name):
        try:
            i = ObjectPrinter.ORDER.index(name)
        except ValueError:
            # If no match, place it after things that did match.
            i = len(ObjectPrinter.ORDER)
        return "_%3d%s" % (i, name)


class CollectionPrinter:

    def prettyprint(self, path, name, col):
        if col in printed:
            return
        printed.add(col)

        print(path)
        print('\t__len__: %d' % len(col))
        for i, item in enumerate(col):
            if hasattr(item, 'name'):
                index = "'%s'" % item.name
            else:
                index = "%d" % i
            childpath = "{p}[{i}]".format(p=path, i=index)
            #print(childpath)
            cls = qualname(item)
            dispatch(childpath, index, item)


class TextPrinter:

    def prettyprint(self, path, name, text):
        if text in printed:
            return
        printed.add(text)

        for line in text.lines:
            print('\t%s' % line.body)


class NullPrinter:

    def prettyprint(self, path, name, ob):
        return


class ReprPrinter:

    def prettyprint(self, path, name, ob):
        print('\t{name}: {value}'.format(name=name, value=repr(ob)))


repr_printer = ReprPrinter()

HANDLERS['builtins.builtin_function_or_method'] = NullPrinter()
HANDLERS['builtins.str'] = repr_printer
HANDLERS['builtins.int'] = repr_printer
HANDLERS['builtins.float'] = repr_printer
HANDLERS['builtins.bool'] = repr_printer
HANDLERS['_default'] = ObjectPrinter()
HANDLERS['builtins.bpy_prop_collection'] = CollectionPrinter()
HANDLERS['bpy_types.Text'] = TextPrinter()

printer = ObjectPrinter()
printer.prettyprint('bpy.data', 'data', bpy.data)
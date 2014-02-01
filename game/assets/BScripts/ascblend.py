import bpy

HANDLERS = {}
IGNORE = {
    'bl_rna',
    'particle_edit', # causes crash
    'rna_type',
    'screens',
    'type_info',
    'window_managers',
    'worlds'}

printed = set()

def qualname(ob):
    return '%s.%s' % (ob.__class__.__module__, ob.__class__.__name__)

class ObjectPrinter:

    def prettyprint(self, path, name, ob):
        try:
            if ob in printed:
                print("%s (rpt)" % path)
                return
            printed.add(ob)
        except TypeError:
            return
        else:
            print(path)

        for attr in dir(ob):
            if attr.startswith('__'):
                continue
            if attr in IGNORE:
                continue
            child = getattr(ob, attr)
            cls = qualname(child)
            childpath = "{p}.{col}".format(p=path, col=attr)
            if cls in HANDLERS:
                HANDLERS[cls].prettyprint(childpath, attr, child)
            else:
                HANDLERS['_default'].prettyprint(childpath, attr, child)


class CollectionPrinter:

    def prettyprint(self, path, name, col):
        if col in printed:
            return
        printed.add(col)

        print(path)
        print('\tlength', len(col))
        for i, item in enumerate(col):
            if hasattr(item, 'name'):
                index = "'%s'" % item.name
            else:
                index = "%d" % i
            childpath = "{p}[{i}]".format(p=path, i=index)
            #print(childpath)
            cls = qualname(item)
            if cls in HANDLERS:
                HANDLERS[cls].prettyprint(childpath, index, item)
            else:
                HANDLERS['_default'].prettyprint(childpath, index, item)


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
HANDLERS['_default'] = ObjectPrinter()
HANDLERS['builtins.bpy_prop_collection'] = CollectionPrinter()
HANDLERS['bpy_types.Text'] = TextPrinter()

printer = ObjectPrinter()
printer.prettyprint('bpy.data', 'data', bpy.data)
import bpy

HANDLERS = {}

class Printer:

    IGNORE = {'screens', 'window_managers', 'worlds'}

    def prettyprint(self, path, ob):
        for name, col in self.collections(ob):
            for i, item in enumerate(col):
                if hasattr(item, 'name'):
                    index = "'%s'" % item.name
                else:
                    index = "%d" % i
                childpath = "{p}.{col}[{i}]".format(p=path, col=name, i=index)
                print(childpath)
                #print(repr(item))
                cls = self.qualname(item)
                if cls in HANDLERS:
                    HANDLERS[cls].prettyprint(childpath, item)
                else:
                    self.prettyprint(childpath, item)

    def qualname(self, ob):
        return '%s.%s' % (ob.__class__.__module__, ob.__class__.__name__)

    def collections(self, ob):
        for name in dir(ob):
            if name.startswith('__'):
                continue
            if name in self.IGNORE:
                continue
            child = getattr(ob, name)
            if child.__class__.__name__ == 'bpy_prop_collection':
                yield name, child


class TextPrinter(Printer):

    def prettyprint(self, path, ob):
        for line in ob.lines:
            print('\t%s' % line.body)

HANDLERS['bpy_types.Text'] = TextPrinter()

printer = Printer()
printer.prettyprint('bpy.data', bpy.data)

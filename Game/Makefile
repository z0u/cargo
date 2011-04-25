all: foliage

foliage: OutdoorsGrass_compiled.blend

OutdoorsGrass_compiled.blend: OutdoorsGrass.blend Level1.blend GrassBlade.blend BScripts/BlendKDTree.py
	blender --factory-startup -b OutdoorsGrass.blend -P BScripts/BlendKDTree.py -- OutdoorsGrass_compiled.blend

SCRIPT_CACHE=bxt/*.pyc\
	bxt/__pycache__\
	Scripts/*.pyc\
	Scripts/__pycache__\
	BScripts/*.pyc\
	BScripts/__pycache__

clean:
	rm -rf $(SCRIPT_CACHE)
	rm -f *.blend?
	rm -f *_compiled.blend

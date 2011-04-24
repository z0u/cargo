all: foliage

foliage: OutdoorsGrass_compiled.blend

OutdoorsGrass_compiled.blend: OutdoorsGrass.blend Level1.blend GrassBlade.blend BScripts/BlendKDTree.py
	blender --factory-startup -b OutdoorsGrass.blend -P BScripts/BlendKDTree.py -- OutdoorsGrass_compiled.blend

clean:
	rm -f *.blend?
	rm -f *_compiled.blend

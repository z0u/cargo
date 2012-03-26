all: foliage

# Foliage is compiled: particle system object instances are made real, then
# organised as a KD-tree. See BScripts/BlendKDTree.py
foliage: OutdoorsBase_flowers.blend OutdoorsBase_grass.blend

OutdoorsBase_grass.blend: OutdoorsBase.blend GrassBlade.blend BScripts/BlendKDTree.py
	blender --factory-startup -b OutdoorsBase.blend -P BScripts/BlendKDTree.py -- Grass_LOD OutdoorsBase_grass.blend

OutdoorsBase_flowers.blend: OutdoorsBase.blend GrassBlade.blend BScripts/BlendKDTree.py
	blender --factory-startup -b OutdoorsBase.blend -P BScripts/BlendKDTree.py -- Flowers_LOD OutdoorsBase_flowers.blend

SCRIPT_CACHE=bxt/*.pyc\
	bxt/__pycache__\
	Scripts/*.pyc\
	Scripts/__pycache__\
	BScripts/*.pyc\
	BScripts/__pycache__\
	__pycache__\
	*.pyc\
	*~

clean:
	rm -rf $(SCRIPT_CACHE)
	rm -f *.blend?

distclean: clean
	rm -f OutdoorsBase_grass.blend OutdoorsBase_flowers.blend
	rm -f *.bgeconf


# Path to blender executable.
# Override this if you want to use a version of Blender that is not on the
# system path, e.g. a special build. You can override it by starting the build
# like this:
#
#     make BLENDER=~/local/blender-2.69-6d8f76c-linux-glibc211-x86_64/blender
#
BLENDER := `which blender`

all: foliage


# Foliage is compiled: particle system object instances are made real, then
# organised as a KD-tree. See BScripts/BlendKDTree.py
foliage: OutdoorsBase_flowers.blend OutdoorsBase_grass.blend

OutdoorsBase_grass.blend: OutdoorsBase.blend GrassBlade.blend BScripts/BlendKDTree.py
	$(BLENDER) --factory-startup -b \
		${CURDIR}/OutdoorsBase.blend \
		-P ${CURDIR}/BScripts/BlendKDTree.py -- \
		Grass_LOD ${CURDIR}/OutdoorsBase_grass.blend

OutdoorsBase_flowers.blend: OutdoorsBase.blend GrassBlade.blend BScripts/BlendKDTree.py
	$(BLENDER) --factory-startup -b \
		${CURDIR}/OutdoorsBase.blend \
		-P ${CURDIR}/BScripts/BlendKDTree.py -- \
		Flowers_LOD ${CURDIR}/OutdoorsBase_flowers.blend


clean: SCRIPT_CACHE=bxt/*.pyc \
	bxt/__pycache__ \
	Scripts/*.pyc \
	Scripts/__pycache__ \
	BScripts/*.pyc \
	BScripts/__pycache__ \
	__pycache__ \
	*.pyc \
	*~
clean:
	rm -rf $(SCRIPT_CACHE)
	rm -f *.blend?
	rm -f OutdoorsBase_flowers.blend OutdoorsBase_grass.blend

distclean: clean
	rm -f *.bgeconf


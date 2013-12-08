# Path to blender executable.
# Override this if you want to use a version of Blender that is not on the
# system path, e.g. a special build. You can override it by starting the build
# like this:
#
#     make BLENDER=~/local/blender-2.69-6d8f76c-linux-glibc211-x86_64/blender
#
BLENDER := `which blender`

all: updateversion foliage

# Foliage is compiled: particle system object instances are made real, then
# organised as a KD-tree. See BScripts/BlendKDTree.py
foliage: OutdoorsBase_flowers.blend OutdoorsBase_grass.blend

OutdoorsBase_grass.blend: OutdoorsBase.blend GrassBlade.blend BScripts/BlendKDTree.py
	$(BLENDER) --factory-startup -b OutdoorsBase.blend -P BScripts/BlendKDTree.py -- Grass_LOD OutdoorsBase_grass.blend

OutdoorsBase_flowers.blend: OutdoorsBase.blend GrassBlade.blend BScripts/BlendKDTree.py
	$(BLENDER) --factory-startup -b OutdoorsBase.blend -P BScripts/BlendKDTree.py -- Flowers_LOD OutdoorsBase_flowers.blend

SCRIPT_CACHE=bxt/*.pyc\
	bxt/__pycache__\
	Scripts/*.pyc\
	Scripts/__pycache__\
	BScripts/*.pyc\
	BScripts/__pycache__\
	__pycache__\
	*.pyc\
	*~

# Updates the files to the current Blender version. If this is not done, Blender
# may crash when loading linked assets, because the linked files are not
# converted automatically when being opened.
updateversion:
	@echo Updating files using $(BLENDER)
	@for f in *.blend bat/*.blend ../*.blend; \
	do \
	    echo -n "$$f ... "; \
	    $(BLENDER) -b "$$f" -P BScripts/update_version.py; \
	    echo done; \
	done
	@echo Storing current version in BLENDER_VERSION.txt
	@$(BLENDER) -v > BLENDER_VERSION.txt

clean:
	rm -rf $(SCRIPT_CACHE)
	rm -f *.blend?

distclean: clean
	rm -f *.bgeconf


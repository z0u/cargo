SHELL=/bin/bash

# Path to blender executable.
# Override this if you want to use a version of Blender that is not on the
# system path, e.g. a special build. You can override it by starting the build
# like this:
#
#     make BLENDER=~/local/blender-2.69-6d8f76c-linux-glibc211-x86_64/blender
#
BLENDER := `which blender`

VERSION := $(shell git describe --tags | sed -r s/^v-//)
GAME_NAME := cargo
ASSETS := ../build/assets
DOCS := ../readme.html ../readme_files \
	../VERSION.txt ../BLENDER_VERSION.txt
BLEND_FILES := \
	build/assets/OutdoorsBase_flowers.blend \
	build/assets/OutdoorsBase_grass.blend \
	$(addprefix build/, $(shell cd game; find . -name \*.blend))
FOLIAGE := \
	game/assets/OutdoorsBase_flowers.blend \
	game/assets/OutdoorsBase_grass.blend

.PHONY: dist
dist: dist-osx dist-win dist-lin


# Copy relevant files over to build directory. Note that .blend files are done
# individually using Blender.
.PHONY: build
build: copy-files $(BLEND_FILES)
	echo "$(VERSION)" > VERSION.txt
	$(BLENDER) -v > BLENDER_VERSION.txt

.PHONY: copy-files
copy-files: RSYNC_EXCLUDE := \
	--exclude-from=.gitignore \
	--exclude \*.blend \
	--exclude .git\* \
	--exclude BScripts \
	--exclude pyextra
copy-files:
	mkdir -p build
	rsync $(RSYNC_EXCLUDE) -av game/ build/


# Foliage is compiled: particle system object instances are made real, then
# organised as a KD-tree. See BScripts/BlendKDTree.py
foliage: $(FOLIAGE)

game/assets/OutdoorsBase_%.blend: game/assets/OutdoorsBase.blend game/assets/GrassBlade.blend game/assets/BScripts/BlendKDTree.py
	group=$(notdir $*); \
	group=$${group^}; \
	echo compiling $${group}; \
	$(BLENDER) --factory-startup -b \
		${CURDIR}/game/assets/OutdoorsBase.blend \
		-P ${CURDIR}/game/assets/BScripts/BlendKDTree.py -- \
		$${group}_LOD ${CURDIR}/$@


# Updates the files to the current Blender version. If this is not done, Blender
# may crash when loading linked assets, because the linked files are not
# converted automatically when being opened. Only an issue in blenderplayer.
build/%.blend: game/%.blend
	@mkdir -p $(dir $@)
	$(BLENDER) -b $< -P game/assets/BScripts/update_version.py -- $@


# Package distribution files.
package = \
	@test -n "$(ARCHIVES)" || { echo "Error: no archive files. Download Blender archives and put them in the blender/ directory. See http://www.blender.org/download/get-blender/"; false; }; \
	mkdir -p dist; \
	cd dist; \
	for archive in $(ARCHIVES); do \
		echo Building from $$archive; \
		../package_bge_runtime/package_bge_runtime.py \
			-v $(VERSION) --exclude=../exclude.txt --name=$(GAME_NAME) \
			../$$archive $(MAINFILE) $(ASSETS) --docs $(DOCS) -p1; \
		if [ $$? -ne 0 ]; then exit $$?; fi \
	done


.PHONY: dist-osx
dist-osx: ARCHIVES := $(wildcard blender/*OSX*.zip)
dist-osx: MAINFILE := ../build/cargo_w.blend
dist-osx: build
	$(call package)

.PHONY: dist-win
dist-win: ARCHIVES := $(wildcard blender/*win*.zip)
dist-win: MAINFILE := ../build/cargo.blend
dist-win: build
	$(call package)

.PHONY: dist-lin
dist-lin: ARCHIVES := $(wildcard blender/*linux*.tar.bz2)
dist-lin: MAINFILE := ../build/cargo.blend
dist-lin: build
	$(call package)


.PHONY: clean
clean:
	rm -rf build dist VERSION.txt BLENDER_VERSION.txt
	$(MAKE) -C game/assets clean

.PHONY: clean
distclean:
	rm -rf $(FOLIAGE)
	$(MAKE) -C game/assets distclean


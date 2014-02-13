SHELL=/bin/bash

# Path to blender executable.
# Override this if you want to use a version of Blender that is not on the
# system path, e.g. a special build. You can override it by starting the build
# like this:
#
#     make BLENDER=~/local/blender-2.69-6d8f76c-linux-glibc211-x86_64/blender
#
BLENDER := `which blender`

VERSION := $(shell git describe --tags)
GAME_NAME := cargo
ASSETS := ../build/assets
DOCS := ../readme.html ../readme_files \
	../build/VERSION.txt ../build/BLENDER_VERSION.txt
BLEND_FILES := $(addprefix build/, $(shell cd game; find . -name \*.blend))


.PHONY: dist
dist: compile build dist-osx dist-win dist-lin


compile:
	$(MAKE) -C game/assets foliage


# Copy relevant files over to build directory. Note that .blend files are done
# individually using Blender.
.PHONY: build
build: RSYNC_EXCLUDE := \
	--exclude-from=.gitignore \
	--exclude \*.blend \
	--exclude .git\* \
	--exclude BScripts \
	--exclude pyextra
build: $(BLEND_FILES)
	mkdir -p build
	rsync $(RSYNC_EXCLUDE) -av game/ build/
	echo "$(VERSION)" > build/VERSION.txt
	$(BLENDER) -v > build/BLENDER_VERSION.txt


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
dist-osx:
	$(call package)

.PHONY: dist-win
dist-win: ARCHIVES := $(wildcard blender/*win*.zip)
dist-win: MAINFILE := ../build/cargo.blend
dist-win:
	$(call package)

.PHONY: dist-lin
dist-lin: ARCHIVES := $(wildcard blender/*linux*.tar.bz2)
dist-lin: MAINFILE := ../build/cargo.blend
dist-lin:
	$(call package)


.PHONY : clean
clean:
	rm -rf build dist build/VERSION.txt build/BLENDER_VERSION.txt
	$(MAKE) -C game/assets clean

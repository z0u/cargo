SHELL=/bin/bash

VERSION := $(shell cat VERSION.txt)
GAME_NAME := cargo
ASSETS := ../game/assets
DOCS := ../readme.html ../readme_files

# Compile any generated game files.
compile:
	$(MAKE) -C game/assets

# Package distribution files.
package = \
	@test -n "$(ARCHIVES)" || { echo "Error: no archive files. Download Blender archives and put them in the blender/ directory. See http://www.blender.org/download/get-blender/"; false; }; \
	mkdir -p build; \
	cd build; \
	for archive in $(ARCHIVES); do \
		echo Building from $$archive; \
		../package_bge_runtime/package_bge_runtime.py \
			-v $(VERSION) --exclude=../exclude.txt --name=$(GAME_NAME) \
			../$$archive $(MAINFILE) $(ASSETS) --docs $(DOCS) -p1; \
		if [ $$? -ne 0 ]; then exit $$?; fi \
	done

.PHONY: build
build: build-osx build-win build-lin

.PHONY: build-osx
build-osx: ARCHIVES := $(wildcard blender/*OSX*.zip)
build-osx: MAINFILE := ../game/cargo_w.blend
build-osx:
	$(call package)

.PHONY: build-win
build-win: ARCHIVES := $(wildcard blender/*win*.zip)
build-win: MAINFILE := ../game/cargo.blend
build-win:
	$(call package)

.PHONY: build-lin
build-lin: ARCHIVES := $(wildcard blender/*linux*.tar.bz2)
build-lin: MAINFILE := ../game/cargo.blend
build-lin:
	$(call package)

.PHONY : clean

clean:
	rm -r build

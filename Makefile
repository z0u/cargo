LOCATION=${HOME}/Dropbox/cargo
RSYNC_OPTS=-rtuvh --exclude-from=rsync-exclude.txt
LOCAL_FILES=\
	game\
	Source\
	ConceptArt\
	Tasks*
REMOTE_FILES=\
	"$(LOCATION)/game"\
	"$(LOCATION)/Source"\
	"$(LOCATION)/ConceptArt"\
	"$(LOCATION)/Tasks"*

SHELL=/bin/bash
VERSION := $(shell cat VERSION.txt)

ifeq ($(strip $(TARGET)), linux)
	ARCHIVES := $(wildcard blender/*linux*.tar.bz2)
else ifeq ($(TARGET), windows)
	ARCHIVES := $(wildcard blender/*windows*.zip)
else ifeq ($(TARGET), osx)
	ARCHIVES := $(wildcard blender/*OSX*.zip)
else
	ARCHIVES := $(wildcard blender/*.zip blender/*.tar.bz2)
endif

# Compile any generated game files.
compile:
	$(MAKE) -C game/assets

# Package distribution files.
package:
	@mkdir -p build
	@test -n "$(ARCHIVES)" || { echo "Error: no archive files. Download Blender archives and put them in the blender/ directory. See http://www.blender.org/download/get-blender/"; false; }
	cd build;\
		for archive in $(ARCHIVES); do\
			echo Building from $$archive;\
			../package_bge_runtime/package_bge_runtime.py \
				-v $(VERSION) -x ../.gitignore \
				../$$archive ../game/cargo.blend; \
		done

.PHONY : clean

clean:
	rm -r build

# Publish files to team.
export:
	@rsync ${RSYNC_OPTS} ${LOCAL_FILES} "${LOCATION}/"

test-export:
	@rsync ${RSYNC_OPTS} --dry-run ${LOCAL_FILES} "${LOCATION}/"

export-stomp:
	@rsync ${RSYNC_OPTS} --delete ${LOCAL_FILES} "${LOCATION}/"

test-export-stomp:
	@rsync ${RSYNC_OPTS} --delete --dry-run ${LOCAL_FILES} "${LOCATION}/"

# Import team's changed files.
import:
	@rsync ${RSYNC_OPTS} ${REMOTE_FILES} ./

test-import:
	@rsync ${RSYNC_OPTS} --dry-run ${REMOTE_FILES} ./


SHARED_LOCATION=${HOME}/Dropbox/cargo
RSYNC_OPTS=-rtuvh --exclude-from=rsync-exclude.txt
LOCAL_FILES=\
	Game\
	Source\
	ConceptArt\
	Tasks*
REMOTE_FILES=\
	${SHARED_LOCATION}/Game\
	${SHARED_LOCATION}/Source\
	${SHARED_LOCATION}/ConceptArt\
	${SHARED_LOCATION}/Tasks*

# Compile any generated game files.
compile:
	$(MAKE) -C Game

# Publish files to team.
export:
	rsync ${RSYNC_OPTS} ${LOCAL_FILES} ${SHARED_LOCATION}/

test-export:
	rsync ${RSYNC_OPTS} --dry-run ${LOCAL_FILES} ${SHARED_LOCATION}/

# Import team's changed files.
import:
	rsync ${RSYNC_OPTS} ${REMOTE_FILES} ./

test-import:
	rsync ${RSYNC_OPTS} --dry-run ${REMOTE_FILES} ./


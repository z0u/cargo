LOCATION=${HOME}/Dropbox/cargo
RSYNC_OPTS=-rtuvh --exclude-from=rsync-exclude.txt
LOCAL_FILES=\
	Game\
	Source\
	ConceptArt\
	Tasks*
REMOTE_FILES=\
	"${LOCATION}/Game"\
	"${LOCATION}/Source"\
	"${LOCATION}/ConceptArt"\
	"${LOCATION}/Tasks"*

# Compile any generated game files.
compile:
	$(MAKE) -C Game

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


SHARED_LOCATION=${HOME}/Dropbox/cargo
RSYNC_OPTS=-rtuvh --exclude-from=rsync-exclude.txt --dry-run

# Compile any generated game files.
compile:
	$(MAKE) -C Game

# Publish files to team.
push:
	rsync ${RSYNC_OPTS} Game Source ConceptArt Tasks* ${SHARED_LOCATION}/

# Import team's changed files.
pull:
	rsync ${RSYNC_OPTS} ${SHARED_LOCATION}/Game ${SHARED_LOCATION}/Source ${SHARED_LOCATION}/ConceptArt ${SHARED_LOCATION}/Tasks* ./


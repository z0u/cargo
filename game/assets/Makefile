
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

distclean: clean
	rm -f *.bgeconf


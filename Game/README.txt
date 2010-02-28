== The story so far... ==
Cargo needs to get to the top of a tree, but there is a beehive in the way. In
desperation, you enter the tree at the bottom and try to sneak through the hive.
Hopefully the bees are still outside.

This is a short section of a larger adventure game. You can follow the game's
development on Alex's blog:

    http://phatcore.com/alex/?cat=8

Thanks for playing!

== To start the game ==
 1. Install Blender 2.49b,  either from the Blender web site or using your
    system's package manager (e.g. apt-get in Debian and Ubuntu Linux). The
    download page for Blender is: 

    http://www.blender.org/download/get-blender/
 
 2. a. Double-click on Dungeon.blend, or 
    b. Start Blender browse to Dungeon.blend using the File > Open
       interface, and then choose Game > Start Game (from the menu at the top).

== Playing the game ==
Cargo can crawl on almost any surface, including walls and ceilings. Use the
arrow keys to move. To turn a corner, press the left or right arrow and forward
or backward - as if you were driving a car.

Cargo's shell is useful, too! Press Space to enter the shell. You can then roll
along the ground by pressing the arrow keys. The shell won't stick to walls or
the ceiling, but it can float. Are there any other uses for it?

== Troubleshooting ==
GNU/Linux:
 1. On systems with PulseAudio installed (such as Ubuntu 9.04+), Blender may
    have trouble playing the sound. If there is no sound, try running Blender
    through padsp:
    
        padsp blender

    If the sound stutters, quit from the game (press Escape) and restart the
    sound server:
    
        pulseaudio -k

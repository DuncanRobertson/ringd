ringd
=====

NOTE: this is quite old code, but just sticking it up on githiub in case anyone finds it useful.

This program listens on a modem device for a configurable maximum and
minumum number of rings, after which it will dial into the net for a
certain amount of time (by calling wvdial). Read the code and ini file for
info on the parameters. It also has a "secret handshake" mode where it
will listen for 2 single (or close to single) rings spaced X seconds
apart, with a Y seconds tolerance.. For example it can initiate a net
connection on receipt of 2 single phone rings, spaced 74 seconds apart,
give or take 2 seconds. How this set up is documented in the example .ini
file.

The software at the other end to dial a single ring X seconds apart a
single ring is left up to you!

This is a re-implementation of the old perl program "ringd" in python. It
uses some paramater names from the old one but otherwise is re-written
from scratch to suit my requirements. It is rough, but is in production
now. It has some code for dealing with bodgy drivers, i.e. the example ini
file will unload modules if the open() on the modem device hangs. This is
handy for dealing with flaky linmodem drivers.

For total reliability set it to re-start in crontab. If there is already
one running it will die silently.

This program is made available as is under the GNU GPL, see the file
COPYING for details.

Duncan Robertson

duncan@linuxbandwagon.com
http://www.linuxbandwagon.com/

22/8/2001

- Version 0.2 released 26/5/2002
- Added to github June 2014

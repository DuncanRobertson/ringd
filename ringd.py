#!/usr/bin/python
#
version = 'version 0.2'
author  = 'duncan@linuxbandwagon.com'
#
#  $Id: ringd.py,v 1.17 2002/05/06 14:46:24 master Exp $
#
#  Simple re-implementation of the old perl ringd program in python.
#
#  Does not do as much logging.
#
#   duncan@linuxbandwagon.com
#
#  THIS SOFTWARE IS COPYRIGHT 2001,2002 Linuxbandwagon Pty. Ltd. Australia
#  and is released under the GPL. NO WARRANTY!!!
#  see http://www.gnu.org/copyleft/gpl.html for further info.
#
#
# developed on python 1.5.2 on redhat 7
#
# This is an early python effort from me, and written rapidly to fill a
# need.
#
# 30/4/2002 - 0.2 -- added "secret knock" for 2 single rings spaced 
#                    a certain time apart
#                    as the dialout signature.
#

cvsid = '$Id: ringd.py,v 1.17 2002/05/06 14:46:24 master Exp $'

debugon = 0

inifile = 'ringd.ini'

import sys, commands, os, time, glob, pty, getopt, ConfigParser, string, signal

ringcount = 0
readfrommodem = ''

def nulltimer(signun, frame):
   debug('nulltimer called')

def opentimer(signum, frame):
   debug('opentimer called')
   raise IOError, "open() hanging"

def ringingtimer(signum, frame):
   global readfrommodem
   debug('ringingtimer triggered')
   readfrommodem = ''

def ringingtimer2(signum, frame):
   global readfrommodem, timeover
   debug('ringingtimer triggered')
   readfrommodem = ''
   timeover = 1

def netdowntimer(signum, frame):
   global pollingperiod, netupfile, systemname

   debug('netdowntimer tiggered')
   #
   if os.path.isfile(netupfile):
      debug('found file '+netupfile+' so we dont want to kill the net yet')
      #
      #  set an allarm for pollingperiod seconds.
      debug('setting alarm to trigger in '+str(pollingperiod)+' seconds')
      signal.signal(signal.SIGALRM, netdowntimer)
      signal.alarm(pollingperiod)
   else:
      debug('running pppstop command '+pppstop)
      returncode = os.system(pppstop)
      if returncode != 0:
         print systemname+': error running '+pppstop
         # sys.exit(1)

def debug(debuginfo):
   if debugon == 1:
      print debuginfo

#
#  sanity checking on config files (or other files that need to be there)
#
def checkexists(filename):
   if not os.path.isfile(filename):
      print 'Error: '+filename+' is not a file'
      sys.exit(1)

def make_lock_file(lockfilename):
   global systemname
   #
   # first open the lock file
   #
   if os.access(lockfilename,os.R_OK):
      try:
         fo = open(lockfilename, 'r')
      except IOError:
         print systemname+': Can\'t open lock file for reading.'
         sys.exit(3)
      pidstring = fo.read()
      debug('pid found in lockfile is ' + pidstring)
      res = commands.getstatusoutput('kill -0 ' + pidstring)
      if res[0] != 0:
         print systemname+': process '+pidstring+' found in lock file seems dead'
      else:
         debug('Existing process detected, bailing out..')
         fo.close()
         sys.exit(3)

   try:
      fi = open(lockfilename, 'w')
   except IOError:
      print systemname+': Can\'t open lock file for writing.'
      sys.exit(0)
   fi.write(`os.getpid()`)
   fi.close();

def usage(progname):
   print progname
   print version
   print author
   print
   print 'Usage:'
   print progname+' <flags>'
   print
   print 'where <flags> can be any of:'
   print '   --debug      (debug output on)'
   print '   --help       (print this message and quit)'
   print '   --config <filename> config file to use, default is '+inifile
   print

#
#  fork off and run the ppp command
#
def forknet(pppstart):
   debug('forking and running pppstart command '+pppstart) 
   if os.fork() == 0:
      res = commands.getstatusoutput(pppstart)
      if res[0] != 0:
         print systemname+': error running '+pppstart
         print res[1]
         sys.exit(1)
      else:
         debug('output from command was')
         debug(res[1])
         sys.exit(0)

#
# implements the simpler ring pattern mode - just a certain amount
# of rings within a certain timeframe.
# return 1 if net connection attempted, 0 otherwise
#

def nonpatternmoderingdetect(sfile,ringstring,timewindowtoinitiatenet,counttostartnet,counttonotstartnet,pppstart):
   global readfrommodem

   ringcount = 0
   while 1:
      try:
         readfrommodem = os.read(sfile,100)
      except OSError:
         debug('interupted, time is probably up')
      if len(readfrommodem) == 0:
         debug('0 length read from modem')
         os.close(sfile)
         break

      debug('read from modem')
      debug('['+readfrommodem+']')
      if string.find(readfrommodem,ringstring) != -1:
         ringcount = ringcount + 1
         debug('ring detected '+str(ringcount))
         if ringcount == 1:
            debug('setting alarm to trigger in '+str(timewindowtoinitiatenet)+' seconds')
            signal.signal(signal.SIGALRM, ringingtimer)
            signal.alarm(timewindowtoinitiatenet)

   if ringcount >= counttostartnet and ringcount < counttonotstartnet:
      try:
         os.close(sfile)
      except OSError:
         debug('error closing modem, prolly closed already, thats ok')
      debug(str(counttostartnet)+'or more rings, but less than '+str(counttonotstartnet))
      debug(str(ringcount)+' rings detected, waiting to dial net')
      debug('sleeping '+str(delaybeforestartingnet)+\
         ' seconds to before starting net')
      time.sleep(delaybeforestartingnet)
      forknet(pppstart)
      return 1
   else:
      return 0

#
# implements a more careful ring pattern ... X rings, then ignoring 
# any rings for Y seconds.. then X rings. This is so hopefully we can
# give the system 2 single rings spaced X seconds apart as the "secret
# knock" so that the system knows we want it to dial out.
#
# this way should be less prone to restart problems, etc, as we keep
# a list of the times when we detect a single ring, and sort through 
# them looking for the right gap, which is a way nicer way to do
# it.....
#
def patternmoderingdetect(sfile,ringstring,timewindowtoinitiatenet,counttostartnet,counttonotstartnet,pppstart,configs):
   global readfrommodem, timeover
   singlerings = []   # list of when single rings have occurred 

   # not used yet - for now just 1 ring is da signal
   # patternrings = configs.getint('ringd','patternrings')
   patterndelay = configs.getint('ringd','patterndelay')
   patternwindow = configs.getint('ringd','patternwindow')

   nowindow = 1
   ringcount = 0
   timeover  = 0
   while nowindow:
      try:
         readfrommodem = os.read(sfile,100)
      except OSError:
         debug('interupted, time is probably up')
      if len(readfrommodem) == 0:
         debug('0 length read from modem')

      debug('read from modem')
      debug('['+readfrommodem+']')
      if string.find(readfrommodem,ringstring) != -1:
         ringcount = ringcount + 1
         debug('ring detected '+str(ringcount))
         if ringcount == 1:
            ringtime = int(time.time())
            debug('setting alarm to trigger in '+str(patternwindow)+' seconds')
            signal.signal(signal.SIGALRM, ringingtimer2)
            signal.alarm(patternwindow)

      if ringcount != 1:
            debug('not just one ring detected, not the start of a pattern')
      else:
         if timeover == 1:
            debug('single ring detected, adding to list')
            singlerings.append(ringtime)
            debug(singlerings)

         # now check the singlerings list to see if any patterndelay 
         # plus or minus patternwindow seconds apart....
         for ringtime2 in singlerings:
            diff = ringtime - ringtime2
            debug('seconds apart '+str(diff))
            if (diff > (patterndelay - (patternwindow / 2))) and \
               (diff < (patterndelay + (patternwindow / 2))):
               debug('CORRECT WINDOW FOUND!')
               nowindow = 0
               signal.alarm(0)
            if (ringtime - ringtime2) > (patterndelay + patternwindow):
               debug('old ring removed '+str(diff))
               singlerings.remove(ringtime2)

      if timeover == 1:
         timeover = 0
         ringcount = 0

   try:
      os.close(sfile)
   except OSError:
      debug('error closing modem, prolly closed already, thats ok')
   debug('wating '+str(delaybeforestartingnet)+' seconds before starting the net')
   time.sleep(delaybeforestartingnet)
   forknet(pppstart)
   return 1

#
# main() bit
#
try:
    options, xarguments = getopt.getopt(sys.argv[1:],
    'dvc',['debug','verbose','config='])
except getopt.error:
   usage(sys.argv[0])
   sys.exit(1)

for a in options[:]:
   if a[0] == '--config' and a[1] != '':
      inifile =  a[1]
      debug('using config file '+a[1])
      options.remove(a)
   if a[0] == '--help':
      print CVSID
      usage(sys.argv[0])
      sys.fexit(0)
   if a[0] == '--debug':
      debugon = 1
      debug('setting debug output on')
   if a[0] == '--verbose':
      verboseon = 1
      verbose('setting verbose output')

debug(version)
debug(author)

if len(xarguments) != 0:
   usage(sys.argv[0])
   sys.exit(1)

#
#  read in the config settings
#
configs = ConfigParser.ConfigParser()
checkexists(inifile)
configs.read(inifile)

lockfile = configs.get('ringd','lockfile')
systemname = configs.get('system','name')

make_lock_file(lockfile)

#
#  get the rest of the parameters from the config file
#
modem = configs.get('ringd','modem')
stty = configs.get('ringd','stty')
pppstart = configs.get('ringd','pppstart')
resetdevice = configs.get('ringd','resetdevice')
netupfile = configs.get('ringd','netupfile')
pppstop = configs.get('ringd','pppstop')
checknet = configs.get('ringd','checknet')
counttostartnet = configs.getint('ringd','counttostartnet')

#
# if this option doesnt exist we set it to 2 more than
# the minimum number of rings.
#
if 'counttonotstartnet' in configs.options('ringd'):
   counttonotstartnet = configs.getint('ringd','counttonotstartnet')
else:
   counttonotstartnet = counttostartnet + 2

if 'patternmode' in configs.options('ringd'):
   patternmode = configs.getint('ringd','patternmode')
else:
   patternmode = 0

timewindowtoinitiatenet = configs.getint('ringd','timewindowtoinitiatenet')
delaybeforestartingnet = configs.getint('ringd','delaybeforestartingnet')
netuptime = configs.getint('ringd','netuptime')
delayafterkillingnet = configs.getint('ringd','delayafterkillingnet')
pollingperiod = configs.getint('ringd','pollingperiod')
initstring = configs.get('ringd','initstring')
ringstring = configs.get('ringd','ringstring')


running = 1
netup = 0

while running:
   #
   #  test if the net is up, if not kill any ppp crap around
   #
   debug('running checknet command '+checknet)
   res = commands.getstatusoutput(checknet)
   debug('checknet command gave output was '+res[1])
   if res[0] == 0:   
      netup = 1
   else:
      debug('running pppstop command '+pppstop)
      #
      #  maybe check for /tmp/keepnetup
      #  to postpone net shutdown?
      #
      # get rid of any net down signals hanging about (or others)
      signal.alarm(0)
      returncode = os.system(pppstop)
      if returncode != 0:
         print 'error running '+pppstop
         # sys.exit(1)
      netup = 0

   if netup:
      debug('net still seems to be up, sleeping')
      try:
         time.sleep(pollingperiod)
      except IOError:
         debug('interupted, net has probably been killed')
   else:
      debug('setting alarm to trigger in '+str(5)+' seconds')
      signal.signal(signal.SIGALRM, opentimer)
      signal.alarm(5)
      try:
         sfile = os.open(modem,os.O_RDWR)
      except:
         debug('problem opening modem, lets run the modem reset command')
         #
         # modem is hanging, maybe driver jammed or who knows what, 
         # reloading the modules seems to work for Lucent LinModems
         res = commands.getstatusoutput(resetdevice)
         if res[0] != 0:
            print systemname +': error running '+resetdevice
            print res[1]
            sys.exit(1)
         else:
            debug('output from command '+resetdevice+' was')
            debug(res[1])
            sys.exit(0)

         continue
      signal.alarm(0)
      command = stty+' < '+modem
      debug('stty command is')
      debug(command)
      res = commands.getstatusoutput(command)
      if res[0] != 0:
         print 'Error Couldnt set serial port parameters for '+modem
         print res[1]
         # sys.exit(1)
         os.close(sfile)
         debug('sleeping '+ str(pollingperiod))
         try:
            time.sleep(pollingperiod)
         except IOError:
            debug('interupted, net has probably been killed')
         continue

      debug('initialising modem with initstring')
      debug(initstring)

      os.write(sfile,initstring+'\r')


      #
      # wait around for the phone to ring, in a pattern we want...
      #
      if patternmode == 0:
         netcalled = nonpatternmoderingdetect(sfile,ringstring,timewindowtoinitiatenet,counttostartnet,counttonotstartnet,pppstart)
      if patternmode == 1:
         netcalled = patternmoderingdetect(sfile,ringstring,timewindowtoinitiatenet,counttostartnet,counttonotstartnet,pppstart,configs)

      if netcalled == 1:
         # we have
         # found a ring pattern that is agreeable to us, and tried to 
         # start the net, so now we just wait and see if things are OK.
         #
         # set alarm to kill net connection in X seconds
         #
         debug('setting alarm to trigger in '+str(netuptime)+' seconds')
         signal.signal(signal.SIGALRM, netdowntimer)
         signal.alarm(netuptime)

         #
         #  loop around and check the net, after a delay
         #
         debug('sleeping '+str(pollingperiod)+' before checking net') 
         try:
            time.sleep(pollingperiod)
         except IOError:
            debug('interupted, net has probably been killed')

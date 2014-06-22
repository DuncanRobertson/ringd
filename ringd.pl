#!/usr/bin/perl
###############################################################################
# Ring Daemon
# Version 0.95 5 June 1995  Ken Neighbors
#
#  Copyright (C) 1995  W. Ken Neighbors III - ken@best.com
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
###############################################################################
#
# Listens to the modem for phone rings.  If a certain number of rings occur
# in a certain length of time, it is interpreted as a request to initiate
# a net connection.
#
# The net connection is terminated after $NetUpTime unless
# the file /tmp/KeepNetUp exists.

# Command to bring the net connection up, e.g., "ppp-on"
# If you're using dip, you may want to use the '-v' option for
# debugging.  Once you know it works, you can get rid of it.
$NetUpCommand = "/sbin/dip -v ~/lib/stanford.dip";

# Command to bring down the net connection, e.g., "ppp-off"
$NetDownCommand = "/sbin/dip -k";

# Command to check and make sure the net connection is still up.
# (If this command returns false, ringd will hangup the modem and
# start listening for rings again).
$NetCheckCommand = "ping -c 1 Avallone.Stanford.EDU >/dev/null 2>&1";

# Command to notify someone that the net is up.  It is passed two
# additional arguments, the time that the net was brought up and how
# long it will stay up.  If you have a dynamically assigned ip address,
# then hopefully the program will include it in the notification.  Leave
# blank for no notification.
$NotifyCommand = "ringd-notify `whoami`@leland.stanford.edu";

$LogFileName = "/tmp/ringd.log";

# Parameters for detecting a net request
$CountToInitiateNet = 6;	# number of rings
$TimeWindowToInitiateNet = 80;  # in how many seconds

# How long to wait for answering machine and phone to settle back down
# after detecting a net connection request
$DelayBeforeStartingNet = 30; # in seconds

# How long to keep net up after detecting a net connection request
$NetUpTime = 600; # in seconds

# How long to wait after killing net connection before restarting the
# ring daemon
$DelayAfterKillingNet = 20; # in seconds

# How often to check for existance of /tmp/KeepNetUp files
$PollingPeriod = 60; # in seconds

# Where's the modem:
$Device = "/dev/modem";
# For debugging, uncomment the following:
#$DebugDevice = "/dev/tty";

##########################################################################

@wdays = (Sun,Mon,Tue,Wed,Thu,Fri,Sat);
@months = (Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov,Dec);

($sec,$min,$hour,$mday,$mon,$year,$wday,$yday,$isdst) = localtime(time);
&LogMsg( sprintf( "\n***** ringd started at %02d:%02d:%02d on %s, %d %s %d.\n",
		 $hour, $min, $sec,
		 $wdays[$wday], $mday, $months[$mon], $year ) );

&LogMsg( "Device is '$Device'.\n" );
if ( $DebugDevice )
{
    &LogMsg( "However, debugging is enabled, and so ringd\n" );
    &LogMsg( "is listening to '$DebugDevice' for RING strings.\n" );
    $Device = $DebugDevice;
}

# Modem setup commands
# speed is set to 56700 bps for 38400 request
system( "setserial $Device spd_hi" );
# raw transparent terminal settings
system( "stty 5:0:80000c8f:0:0:0:0:0:0:0:1:0:0:0:0:0:0:0:0:0:0:0:0 <$Device" );
# set speed
system( "stty 38400 < $Device" );

for (;;) {

    # enable auto-flushing of print commands
    $| = 1;

    $ModemOpenDelay = 15;
    $ModemOpenDelayMax = 120;
    $ModemOpenTries = 20;
    while ( ! open( MODEM, "<$Device" ) )
    {
	&LogMsg( "Couldn't talk to modem: $!\n" );
	&LogMsg( "Will wait and try again in $ModemOpenDelay seconds\n" );
	sleep $ModemOpenDelay;
	if ( $ModemOpenDelay < $ModemOpenDelayMax )
	{
	    $ModemOpenDelay += 15;
	}
	--$ModemOpenTries;
	if ( ! $ModemOpenTries )
	{
	    die "Giving up.\n";
	}
    }
    vec( $rin, fileno( MODEM ), 1 ) = 1;

    # clear out any queued up garbage from the modem
    do {
	$nfound = select( $rout=$rin, undef, undef, 2 );
	if ( $nfound ) {
	    $_ = <MODEM>;
	}
    } until ( !$nfound || !$_ );

    ($sec,$min,$hour,$mday,$mon,$year,$wday,$yday,$isdst) = localtime(time);
    &LogMsg( sprintf( "It is now %02d:%02d:%02d on %s, %d %s %d.\n",
		     $hour, $min, $sec,
		     $wdays[$wday], $mday, $months[$mon], $year ) );
    &LogMsg( "Waiting for $CountToInitiateNet rings in " );
    &LogMsg( "$TimeWindowToInitiateNet seconds\n" );
    &LogMsg( "as a signal to start net connection.\n" );

    # listen for rings
    do {
	$_ = <MODEM>;
	if ( ! $_ )
	{
	    &LogMsg( "Error:  modem in use?  Will try again in 5 seconds.\n" );
	    sleep 5;
	    close( MODEM );
	    &LogMsg( "Trying again . . . \n" );
	    while ( ! open( MODEM, "<$Device" ) )
	    {
		&LogMsg( "Couldn't talk to modem: $!\n" );
		&LogMsg( "Will wait and try again in 15 seconds\n" );
		sleep 15;
	    }
	}
	# for debugging, uncomment the following line
	#s/\s*$//; print "Got '$_'.\n";
	if ( /RING/ )
	{
	    $Time = time;
	    push( RingArray, $Time );
	    ($sec,$min,$hour,$mday,$mon,$year,$wday,$yday,$isdst) =
		localtime($Time);
	    &LogMsg( sprintf(
			     "Phone rang at %02d:%02d:%02d on %s, %d %s %d.\n",
			     $hour, $min, $sec,
			     $wdays[$wday], $mday, $months[$mon], $year ) );
	}
    } until &NetRequest( @RingArray );

    undef @RingArray;
    close( MODEM );

    &LogMsg( sprintf( "Detected net connection request at %02d:%02d:%02d.\n",
	   $hour, $min, $sec ) );
    &LogMsg( "Initiating connection in " );
    &LogMsg( "$DelayBeforeStartingNet seconds.\n" );
    sleep $DelayBeforeStartingNet;

    &LogMsg( "Initiating net connection . . .\n" );
    $NetDied = 0;
    system( $NetUpCommand );
    &LogMsg( "Net is (probably) up.\n" );

    # Create the file /tmp/KeepNetUp$NetUpTime
    open( TMP, ">>/tmp/KeepNetUp$NetUpTime" );
    close( TMP );

    ($sec,$min,$hour,$mday,$mon,$year,$wday,$yday,$isdst) = localtime(time);
    $NetUpAt = sprintf( "%02d:%02d:%02d", $hour, $min, $sec );

    &LogMsg( "/tmp/KeepNetUp$NetUpTime will be deleted " );
    &LogMsg( "in $NetUpTime seconds.\n" );
    unless ($rmpid = fork) {
	# this is the child process
	sleep $NetUpTime;
	system( "rm -f /tmp/KeepNetUp$NetUpTime" );
	exit 0
    }

    # Notify someone that the net is up.
    if ( $NotifyCommand )
    {
	if ( 0 == system( $NetCheckCommand ) )
	{
	    $NotifyCommandLine = "$NotifyCommand $NetUpAt $NetUpTime";
	    &LogMsg( "Notifying: $NotifyCommandLine\n" );
	    system( $NotifyCommandLine );
	}
	else
	{
	    &LogMsg( "Net isn't up?  Can't notify.\n" );
	}
    }

    &LogMsg( "Waiting for /tmp/KeepNetUp$NetUpTime to be deleted.\n" );
    do {
	sleep $PollingPeriod;
	# check to see if net is down
	if ( 0 != system( $NetCheckCommand ) ) {
	    $NetDied = 1;
	    kill 9, $rmpid;
	    system( "rm -f /tmp/KeepNetUp$NetUpTime" );
	}
    } while ( -e "/tmp/KeepNetUp$NetUpTime" );
    &LogMsg( "/tmp/KeepNetUp$NetUpTime was deleted.\n" );

    if ( -e "/tmp/KeepNetUp" ) {
	if ( $NetDied ) {
	    system( "rm -f /tmp/KeepNetUp" );
	}
	else {
	    &LogMsg( "Waiting for /tmp/KeepNetUp to be deleted.\n" );
	}
    }
    while ( -e "/tmp/KeepNetUp" ) {
	sleep $PollingPeriod;
	# check to see if net is down
	if ( 0 != system( $NetCheckCommand ) ) {
	    $NetDied = 1;
	    kill 9, $rmpid;
	    system( "rm -f /tmp/KeepNetUp" );
	}
    }
    &LogMsg( "/tmp/KeepNetUp was deleted.\n" );
    sleep 10;

    if ( $NetDied ) {
	($sec,$min,$hour,$mday,$mon,$year,$wday,$yday,$isdst) =
	    localtime(time);
	&LogMsg( "\nNet connection is probably down at %02d:%02d:%02d.\n",
		$hour, $min, $sec);
    }

    &LogMsg( "Terminating net connection . . .\n" );
    system( $NetDownCommand );
    &LogMsg( "Terminated.\n" );

    &LogMsg( "Will restart ring daemon in $DelayAfterKillingNet seconds.\n" );
    sleep $DelayAfterKillingNet;

    &LogMsg( "\n" );
}

exit 0;

sub NetRequest
{
    local( @RingArray ) = @_;
    $Now = pop( @RingArray );
    $Count = 1;
    foreach $Time ( reverse @RingArray )
    {
	++$Count if ( $Now - $Time <= $TimeWindowToInitiateNet );
    }
    return( $Count >= $CountToInitiateNet );
}

sub LogMsg
{
    local( $Message ) = @_;
    print $Message;
    open( LOGFILE, ">> $LogFileName" );
    print LOGFILE $Message;
    close( LOGFILE );
}

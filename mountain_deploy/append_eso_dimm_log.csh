#!/bin/csh
#
# append_eso_dimm_log.csh
#
# Fetch ESO dimm.last and append one UTC-stamped arcsec line to dimm.logs.
# Install on mountain: cp to $LS4_ROOT/bin/ and hook from ntt_dome_status.
#
if ( ! $?LS4_ROOT ) then
   echo "append_eso_dimm_log: LS4_ROOT is not set" >& /dev/stderr
   exit 1
endif

set url = "https://www.ls.eso.org/lasilla/dimm/dimm.last"
if ($?LS4_ESO_DIMM_URL) then
   set url = "$LS4_ESO_DIMM_URL"
endif

set logdir = "$LS4_ROOT/logs"
if ( ! -d $logdir ) mkdir -p $logdir
set log = "$logdir/dimm.logs"
set tmp = "/tmp/eso_dimm_${$}.tmp"

curl -sk --max-time 15 -o $tmp "$url"
if ( $status != 0 || ! -s $tmp ) then
   rm -f $tmp
   exit 1
endif

set line = `cat $tmp`
rm -f $tmp

set arcsec = `echo "$line" | sed -n 's/.*[Ss]eeing=\([0-9.][0-9.]*\).*/\1/p'`
if ( "$arcsec" == "" ) then
   set arcsec = `echo "$line" | awk '{print $1}'`
endif
if ( "$arcsec" == "" ) exit 1

set check = `echo "$arcsec" | awk '{ if ($1 > 0 && $1 < 10) print "ok" }'`
if ( "$check" != "ok" ) exit 1

set stamp = `date -u +"%Y-%m-%dT%H:%M:%SZ"`
echo "$stamp $arcsec" >>! "$log"
exit 0

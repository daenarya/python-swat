#!/usr/bin/env python
# encoding: utf-8
#
# Copyright SAS Institute
#
#  Licensed under the Apache License, Version 2.0 (the License);
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

'''
Utilities for testing

'''

from __future__ import print_function, division, absolute_import, unicode_literals

import os
import re
import unittest

UUID_RE = r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$'


class TestCase(unittest.TestCase):
    ''' TestCase with SWAT Customizations '''

    def assertRegex(self, *args, **kwargs):
        ''' Compatibility across unittest versions '''
        if hasattr(unittest.TestCase, 'assertRegex'):
            return unittest.TestCase.assertRegex(self, *args, **kwargs)
        return self.assertRegexpMatches(*args, **kwargs)

    def assertNotEqual(self, *args, **kwargs):
        ''' Compatibility across unittest versions '''
        if hasattr(unittest.TestCase, 'assertNotEqual'):
            return unittest.TestCase.assertNotEqual(self, *args, **kwargs)
        return self.assertNotEquals(*args, **kwargs)

    def assertEqual(self, *args, **kwargs):
        ''' Compatibility across unittest versions '''
        if hasattr(unittest.TestCase, 'assertEqual'):
            return unittest.TestCase.assertEqual(self, *args, **kwargs)
        return self.assertEquals(*args, **kwargs)

    def assertContainsMessage(self, results, expectedMsg):
        ''' See if expected message is in results '''
        for i in range(len(results.messages)):
            if expectedMsg in results.messages[i]:
                return
        raise ValueError('Expected message not found: ' + expectedMsg)

    def replaceNaN(self, row, nan):
        ''' Replace NaNs in a iterable with specified value '''
        row = list(row)
        for i, x in enumerate(row):
            if pd.isnull(x):
                row[i] = nan
        return row

    def assertTablesEqual(self, a, b, fillna=-999999, sortby=None):
        ''' Compare DataFrames / CASTables '''
        if hasattr(a, 'to_frame'):
            a = a.to_frame()
        if hasattr(b, 'to_frame'):
            b = b.to_frame()
        if sortby:
            a = a.sort_values(sortby)
            b = b.sort_values(sortby)
        self.assertEqual(list(a.columns), list(b.columns))
        a = a.fillna(value=fillna)
        b = b.fillna(value=fillna)
        for lista, listb in zip(list(a.to_records(index=False)),
                                list(b.to_records(index=False))):
            self.assertEqual(list(lista), list(listb))

    def assertColsEqual(self, a, b, fillna=-999999, sort=False):
        ''' Compare Series / CASColumns '''
        if hasattr(a, 'to_series'):
            a = a.to_series()
        if hasattr(b, 'to_series'):
            b = b.to_series()
        a = a.fillna(value=fillna)
        b = b.fillna(value=fillna)
        if sort:
            a = list(sorted(a.tolist()))
            b = list(sorted(b.tolist()))
        else:
            a = a.tolist()
            b = b.tolist()
        self.assertEqual(a, b)


def get_casout_lib(server_type):
    ''' Get the name of the output CASLib '''
    out_lib = os.environ.get('CASOUTLIB', 'CASUSER')
    if '.mpp' in server_type:
        out_lib = os.environ.get('CASMPPOUTLIB', out_lib)
    return out_lib


def get_cas_data_lib(server_type):
    ''' Get the name of data CASLib '''
    data_lib = os.environ.get('CASDATALIB', 'CASTestTmp')
    if '.mpp' in server_type:
        data_lib = os.environ.get('CASMPPDATALIB', 'HPS')
    return data_lib


def get_user_pass():
    ''' 
    Get the username and password from the environment if possible 

    If the environment does not contain a username and password,
    they will be retrieved from a ~/.authinfo file.

    '''
    username = None
    password = None
    if 'CASUSER' in os.environ:
        username = os.environ['CASUSER'] 
    if 'CASPASSWORD' in os.environ:
        password = os.environ['CASPASSWORD'] 
    return username, password


def get_host_port_proto():
    ''' 
    Get the host, port and protocol from a .casrc file 

    NOTE: .casrc files are written in Lua

    Returns
    -------
    (cashost, casport, casprotocol)

    '''
    cashost = os.environ.get('CASHOST')
    casport = os.environ.get('CASPORT')
    casprotocol = os.environ.get('CASPROTOCOL')

    if casport is not None:
        casport = int(casport)

    if cashost and casport:
        return cashost, casport, casprotocol

    # If there is no host or port in the environment, look for .casrc
    casrc = None
    rcname = '.casrc'
    homepath = os.path.join(os.path.expanduser(os.environ.get('HOME', '~')), rcname)
    upath = os.path.join(r'u:', rcname)
    cfgfile = os.path.abspath(os.path.normpath(rcname))

    while not os.path.isfile(cfgfile):
        if os.path.samefile(os.path.dirname(homepath), os.path.dirname(cfgfile)):
            break
        newcfgfile = os.path.abspath(os.path.normpath(rcname)) 
        if os.path.samefile(os.path.dirname(cfgfile), os.path.dirname(newcfgfile)):
            break

    if os.path.isfile(cfgfile):
        casrc = cfgfile
    elif os.path.exists(homepath):
        casrc = homepath
    elif os.path.exists(upath):
        casrc = upath
    else:
        return cashost, casport, casprotocol

    return _read_casrc(casrc)


def _read_casrc(path):
    '''
    Read the .casrc file using Lua 

    Parameters
    ----------
    path : string
        Path to the .casrc file

    Returns
    -------
    (cashost, casport, casprotocol)

    '''
    cashost = None
    casport = None
    casprotocol = None

    if not os.path.isfile(path):
        return cashost, casport, casprotocol

    try:
        from lupa import LuaRuntime
        lua = LuaRuntime()
        lua.eval('dofile("%s")' % path)
        lg = lua.globals()

    except ImportError:
        import subprocess
        import tempfile

        lua_script = tempfile.TemporaryFile(mode='w')
        lua_script.write('''
            if arg[1] then
                dofile(arg[1])
                for name, value in pairs(_G) do
                    if name:match('cas') then
                        print(name .. ' ' .. tostring(value))
                    end
                end
            end
        ''')
        lua_script.seek(0)

        class LuaGlobals(object):
            pass

        lg = LuaGlobals()

        config = None
        try:
            config = subprocess.check_output('lua - %s' % path, stdin=lua_script,
                                             shell=True).strip().decode('utf-8')
        except (OSError, IOError, subprocess.CalledProcessError):
            pass
        finally:
            lua_script.close()

        if config:
            for name, value in re.findall(r'^\s*(cas\w+)\s+(.+?)\s*$', config, re.M):
                setattr(lg, name, value)
        else:
            # Try to parse manually
            config = re.sub(r'\-\-.*?$', r' ', open(path, 'r').read(), flags=re.M)
            for name, value in re.findall(r'\b(cas\w+)\s*=\s*(\S+)(?:\s+|\s*$)', config):
                setattr(lg, name, eval(value))

    try:
       cashost = str(lg.cashost)
    except:
       sys.sterr.write('ERROR: Could not access cashost setting\n')
       sys.exit(1)

    try:
       casport = int(lg.casport)
    except:
       sys.sterr.write('ERROR: Could not access casport setting\n')
       sys.exit(1)

    try:
       if lg.casprotocol:
           casprotocol = str(lg.casprotocol)
    except:
       pass

    return cashost, casport, casprotocol


def load_data(conn, path, server_type, casout=None):
    '''
    If data exists on the server, use it.  Otherwise, upload the data set.

    Parameters
    ----------
    conn : CAS
        The CAS connection
    path : string
        The relative path to the data file
    server_type : string
        The type of CAS server in the form platform.mpp|smp[.nohdfs]
    casout : dict
        The CAS output table specification 

    Returns
    -------
    CASResults of loadtable / upload action

    '''
    import swat.tests as st

    # Get location of data and casout
    data_lib = get_cas_data_lib(server_type)
    out_lib = get_casout_lib(server_type)

    # Remap Windows path separators
    sep = '/'
    if 'win' in server_type:
        sep = '\\'
        path = path.replace('/', '\\')

    if casout is None:
        casout = dict(caslib='casuser')

    if 'caslib' not in casout and 'casLib' not in casout:
        casout['caslib'] = out_lib

    if 'name' not in casout:
        casout['name'] = re.sub(sep, '.', os.path.splitext(path)[0])

    # Try to load server version first
    res = conn.loadtable(caslib=data_lib, path=path, casout=casout)

    # If server version doesn't exist, upload local copy
    if 'tableName' not in res or not res['tableName']:
        #sys.stderr.write('NOTE: Uploading local data file.')
        res = conn.upload(os.path.join(os.path.dirname(st.__file__), path), casout=casout)

    return res


def runtests(xmlrunner=False):
   ''' Run unit tests '''
   import sys

   if '--profile' in sys.argv:
       import profile
       import pstats

       sys.argv = [x for x in sys.argv if x != '--profile']

       if xmlrunner:
           import xmlrunner as xr
           profile.run("unittest.main(testRunner=xr.XMLTestRunner(output='test-reports', verbosity=2))", '_stats.txt')
       else:
           profile.run('unittest.main()', '_stats.txt')

       stats = pstats.Stats('_stats.txt')
       #stats.strip_dirs()
       stats.sort_stats('cumulative', 'calls')
       stats.print_stats(25)
       stats.sort_stats('time', 'calls')
       stats.print_stats(25)

   elif xmlrunner:
       import xmlrunner as xr
       unittest.main(testRunner=xr.XMLTestRunner(output='test-reports', verbosity=2)) 

   else:
       unittest.main()


def get_cas_host_type(conn):
    ''' Return a server type indicator '''
    out = conn.about()
    ostype = out['About']['System']['OS Family']
    stype = 'mpp'
    htype = 'nohdfs'
    if out['server'].ix[0, 'nodes'] == 1:
        stype = 'smp'
    if ostype.startswith('LIN'):
        ostype = 'linux'
    elif ostype.startswith('WIN'):
        ostype = 'windows'
    elif ostype.startswith('OSX'):
        ostype = 'mac'
    else:
        raise ValueError('Unknown OS type: ' + ostype)

    # Check to see if HDFS is present
    out = conn.table.querycaslib(caslib='CASUSERHDFS')
    for key, value in list(out.items()):
       if 'CASUSERHDFS' in key and value:
           # Default HDFS caslib for user exists
           htype = ''

    if stype == 'mpp' and (len(htype) > 0):
        return ostype + '.' + stype + '.' + htype
    else:
        return ostype + '.' + stype


getcashosttype = get_cas_host_type

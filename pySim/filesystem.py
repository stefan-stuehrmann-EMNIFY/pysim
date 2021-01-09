# coding=utf-8
"""Representation of the ISO7816-4 filesystem model.

The File (and its derived classes) represent the structure / hierarchy
of the ISO7816-4 smart card file system with the MF, DF, EF and ADF
entries, further sub-divided into the EF sub-types Transparent, Linear Fixed, etc.

The classes are intended to represent the *specification* of the filesystem,
not the actual contents / runtime state of interacting with a given smart card.

(C) 2021 by Harald Welte <laforge@osmocom.org>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import code

import cmd2
from cmd2 import CommandSet, with_default_category, with_argparser
import argparse

class File(object):
    """Base class for all objects in the smart card filesystem.
    Serve as a common ancestor to all other file types; rarely used directly.
    """
    RESERVED_NAMES = ['..', '.', '/', 'MF']
    RESERVED_FIDS = ['3f00']

    def __init__(self, fid, sfid=None, name=None, desc=None, parent=None):
        if not isinstance(self, ADF) and fid == None:
            raise ValueError("fid is mandatory")
        if fid:
            fid = fid.lower()
        self.fid = fid           # file identifier
        self.sfid = sfid         # short file identifier
        self.name = name         # human readable name
        self.desc = desc         # human readable description
        self.parent = parent
        if self.parent and self.parent != self and self.fid:
            self.parent.add_file(self)
        self.shell_commands = []

    def __str__(self):
        if self.name:
            return self.name
        else:
            return self.fid

    def _path_element(self, prefer_name):
        if prefer_name and self.name:
            return self.name
        else:
            return self.fid

    def fully_qualified_path(self, prefer_name=True):
        """Return fully qualified path to file as list of FID or name strings."""
        if self.parent != self:
            ret = self.parent.fully_qualified_path(prefer_name)
        else:
            ret = []
        ret.append(self._path_element(prefer_name))
        return ret

    def get_mf(self):
        """Return the MF (root) of the file system."""
        if self.parent == None:
            return None
        # iterate towards the top. MF has parent == self
        node = self
        while node.parent != node:
            node = node.parent
        return node

    def _get_self_selectables(self, alias=None):
        """Return a dict of {'identifier': self} tuples"""
        sels = {}
        if alias:
            sels |= {alias: self}
        if self.fid:
            sels |= {self.fid: self}
        if self.name:
            sels |= {self.name: self}
        return sels

    def get_selectables(self):
        """Return a dict of {'identifier': File} that is selectable from the current file."""
        # we can always select ourself
        sels = self._get_self_selectables('.')
        # we can always select our parent
        sels = self.parent._get_self_selectables('..')
        # if we have a MF, we can always select its applications
        mf = self.get_mf()
        if mf:
            sels |= mf.get_app_selectables()
        return sels

    def get_selectable_names(self):
        """Return a list of strings for all identifiers that are selectable from the current file."""
        sels = self.get_selectables()
        return sels.keys()


class DF(File):
    """DF (Dedicated File) in the smart card filesystem.  Those are basically sub-directories."""
    def __init__(self, fid, sfid=None, name=None, desc=None, parent=None):
        super().__init__(fid, sfid, name, desc, parent)
        self.children = dict()

    def __str__(self):
        return "DF(%s)" % (super().__str__())

    def add_file(self, child, ignore_existing=False):
        """Add a child (DF/EF) to this DF"""
        if not isinstance(child, File):
            raise TypeError("Expected a File instance")
        if child.name in File.RESERVED_NAMES:
            raise ValueError("File name %s is a reserved name" % (child.name))
        if child.fid in File.RESERVED_FIDS:
            raise ValueError("File fid %s is a reserved name" % (child.fid))
        if child.fid in self.children:
            if ignore_existing:
                return
            raise ValueError("File with given fid %s already exists" % (child.fid))
        if self.lookup_file_by_sfid(child.sfid):
            raise ValueError("File with given sfid %s already exists" % (child.sfid))
        if self.lookup_file_by_name(child.name):
            if ignore_existing:
                return
            raise ValueError("File with given name %s already exists" % (child.name))
        self.children[child.fid] = child
        child.parent = self

    def add_files(self, children, ignore_existing=False):
        """Add a list of child (DF/EF) to this DF"""
        for child in children:
            self.add_file(child, ignore_existing)

    def get_selectables(self):
        """Get selectable (DF/EF names) from current DF"""
        # global selectables + our children
        sels = super().get_selectables()
        sels |= {x.fid: x for x in self.children.values() if x.fid}
        sels |= {x.name: x for x in self.children.values() if x.name}
        return sels

    def lookup_file_by_name(self, name):
        if name == None:
            return None
        for i in self.children.values():
            if i.name and i.name == name:
                return i
        return None

    def lookup_file_by_sfid(self, sfid):
        if sfid == None:
            return None
        for i in self.children.values():
            if i.sfid == int(sfid):
                return i
        return None

    def lookup_file_by_fid(self, fid):
        if fid in self.children:
            return self.children[fid]
        return None


class MF(DF):
    """MF (Master File) in the smart card filesystem"""
    def __init__(self, fid='3f00', sfid=None):
        super().__init__(fid, sfid, 'MF', 'Master File (directory root)', parent=self)
        self.applications = dict()

    def __str__(self):
        return "MF(%s)" % (self.fid)

    def add_application(self, app):
        """Add an ADF (Application Dedicated File) to the MF"""
        if not isinstance(app, ADF):
            raise TypeError("Expected an ADF instance")
        if app.aid in self.applications:
            raise ValueError("AID %s already exists" % (app.aid))
        self.applications[app.aid] = app

    def get_app_names(self):
        """Get list of completions (AID names)"""
        return [x.name for x in self.applications]

    def get_selectables(self):
        """Get list of completions (DF/EF/ADF names) from current DF"""
        sels = super().get_selectables()
        sels |= self.get_app_selectables()
        return sels

    def get_app_selectables(self):
        # applications by AID + name
        sels = {x.aid: x for x in self.applications.values()}
        sels |= {x.name: x for x in self.applications.values() if x.name}
        return sels



class ADF(DF):
    """ADF (Application Dedicated File) in the smart card filesystem"""
    def __init__(self, aid, fid=None, sfid=None, name=None, desc=None, parent=None):
        super().__init__(fid, sfid, name, desc, parent)
        self.aid = aid           # Application Identifier
        if self.parent:
            self.parent.add_application(self)

    def __str__(self):
        return "ADF(%s)" % (self.aid)

    def _path_element(self, prefer_name):
        if self.name and prefer_name:
            return self.name
        else:
            return self.aid


class EF(File):
    """EF (Entry File) in the smart card filesystem"""
    def __init__(self, fid, sfid=None, name=None, desc=None, parent=None):
        super().__init__(fid, sfid, name, desc, parent)

    def __str__(self):
        return "EF(%s)" % (super().__str__())

    def get_selectables(self):
        """Get list of completions (EF names) from current DF"""
#global selectable names + those of the parent DF
        sels = super().get_selectables()
        sels |= {x.name:x for x in self.parent.children.values() if x != self}
        return sels


class TransparentEF(EF):
    """Transparent EF (Entry File) in the smart card filesystem"""

    @with_default_category('Transparent EF Commands')
    class ShellCommands(CommandSet):
        def __init__(self):
            super().__init__()

        read_bin_parser = argparse.ArgumentParser()
        read_bin_parser.add_argument('--offset', type=int, default=0, help='Byte offset for start of read')
        read_bin_parser.add_argument('--length', type=int, help='Number of bytes to read')
        @cmd2.with_argparser(read_bin_parser)
        def do_read_binary(self, opts):
            """Read binary data from a transparent EF"""
            (data, sw) = self._cmd.rs.read_binary(opts.length, opts.offset)
            self._cmd.poutput(data)

        def do_read_binary_decoded(self, opts):
            """Read + decode data from a transparent EF"""
            (data, sw) = self._cmd.rs.read_binary_dec()
            self._cmd.poutput(data)

        upd_bin_parser = argparse.ArgumentParser()
        upd_bin_parser.add_argument('--offset', type=int, default=0, help='Byte offset for start of read')
        upd_bin_parser.add_argument('data', help='Data bytes (hex format) to write')
        @cmd2.with_argparser(upd_bin_parser)
        def do_update_binary(self, opts):
            """Update (Write) data of a transparent EF"""
            (data, sw) = self._cmd.rs.update_binary(opts.data, opts.offset)
            self._cmd.poutput(data)

        upd_bin_dec_parser = argparse.ArgumentParser()
        upd_bin_dec_parser.add_argument('data', help='Abstract data (JSON format) to write')
        @cmd2.with_argparser(upd_bin_dec_parser)
        def do_update_binary_dec(self, opts):
            """Encode + Update (Write) data of a transparent EF"""
            (data, sw) = self._cmd.rs.update_binary_dec(opts.data)
            self._cmd.poutput(data)

    def __init__(self, fid, sfid=None, name=None, desc=None, parent=None, size={1,None}):
        super().__init__(fid, sfid, name, desc, parent)
        self.size = size
        self.shell_commands += [self.ShellCommands()]

    def decode_bin(self, raw_bin_data):
        """Decode raw (binary) data into abstract representation. Overloaded by specific classes."""
        method = getattr(self, '_decode_bin')
        if callable(method):
            return method(raw_bin_data)
        method = getattr(self, '_decode_hex')
        if callable(method):
            return method(b2h(raw_bin_data))
        return {'raw': raw_bin_data}

    def decode_hex(self, raw_hex_data):
        """Decode raw (hex string) data into abstract representation. Overloaded by specific classes."""
        method = getattr(self, '_decode_hex')
        if callable(method):
            return method(raw_hex_data)
        method = getattr(self, '_decode_bin')
        if callable(method):
            return method(h2b(raw_bin_data))
        return {'raw': h2b(raw_hex_data)}

    def encode_bin(self, abstract_data):
        """Encode abstract representation into raw (binary) data. Overloaded by specific classes."""
        method = getattr(self, '_encode_bin')
        if callable(method):
            return method(abstract_data)
        method = getattr(self, '_encode_hex')
        if callable(method):
            return h2b(method(abstract_data))
        raise NotImplementedError

    def encode_hex(self, abstract_data):
        """Encode abstract representation into raw (hex string) data. Overloaded by specific classes."""
        method = getattr(self, '_encode_hex')
        if callable(method):
            return method(abstract_data)
        method = getattr(self, '_encode_bin')
        if callable(method):
            return b2h(method(abstract_data))
        raise NotImplementedError


class LinFixedEF(EF):
    """Linear Fixed EF (Entry File) in the smart card filesystem"""

    @with_default_category('Linear Fixed EF Commands')
    class ShellCommands(CommandSet):
        def __init__(self):
            super().__init__()

        read_rec_parser = argparse.ArgumentParser()
        read_rec_parser.add_argument('--record-nr', type=int, default=0, help='Number of record to read')

        @cmd2.with_argparser(read_rec_parser)
        def do_read_record(self, opts):
            """Read a record from a record-oriented EF"""
            (data, sw) = self._cmd.rs.read_record(opts.record_nr)
            self._cmd.poutput(data)

        @cmd2.with_argparser(read_rec_parser)
        def do_read_record_decoded(self, opts):
            """Read + decode a record from a record-oriented EF"""
            (data, sw) = self._cmd.rs.read_record_dec(opts.record_nr)
            self._cmd.poutput(data)

        upd_rec_parser = argparse.ArgumentParser()
        upd_rec_parser.add_argument('--record-nr', type=int, default=0, help='Number of record to read')
        upd_rec_parser.add_argument('data', help='Data bytes (hex format) to write')
        @cmd2.with_argparser(upd_rec_parser)
        def do_update_record(self, opts):
            """Update (write) data to a record-oriented EF"""
            (data, sw) = self._cmd.rs.update_record(opts.record_nr, opts.data)
            self._cmd.poutput(data)

        @cmd2.with_argparser(upd_rec_parser)
        def do_update_record_decoded(self, opts):
            """Encode + Update (write) data to a record-oriented EF"""
            (data, sw) = self._cmd.rs.update_record_dec(opts.record_nr, opts.data)
            self._cmd.poutput(data)

    def __init__(self, fid, sfid=None, name=None, desc=None, parent=None, rec_len={1,None}):
        super().__init__(fid, sfid, name, desc, parent)
        self.rec_len = rec_len
        self.shell_commands += [self.ShellCommands()]

    def decode_record_hex(self, raw_hex_data):
        """Decode raw (hex string) data into abstract representation. Overloaded by specific classes."""
        method = getattr(self, '_decode_record_hex')
        if callable(method):
            return method(raw_hex_data)
        method = getattr(self, '_decode_record_bin')
        if callable(method):
            return method(h2b(raw_hex_data))
        return {'raw': h2b(raw_hex_data)}

    def decode_record_bin(self, raw_bin_data):
        """Decode raw (hex string) data into abstract representation. Overloaded by specific classes."""
        method = getattr(self, '_decode_record_bin')
        if callable(method):
            return method(raw_bin_data)
        method = getattr(self, '_decode_record_hex')
        if callable(method):
            return method(b2h(raw_bin_data))
        return {'raw': raw_bin_data}

    def encode_record_hex(self, abstract_data):
        """Encode abstract representation into raw (hex string) data. Overloaded by specific classes."""
        method = getattr(self, '_encode_record_hex')
        if callable(method):
            return method(abstract_data)
        method = getattr(self, '_encode_record_bin')
        if callable(method):
            return h2b(method(abstract_data))
        raise NotImplementedError

    def encode_record_bin(self, abstract_data):
        """Encode abstract representation into raw (binary) data. Overloaded by specific classes."""
        method = getattr(self, '_encode_record_bin')
        if callable(method):
            return method(abstract_data)
        method = getattr(self, '_encode_record_hex')
        if callable(method):
            return h2b(method(abstract_data))
        raise NotImplementedError

class CyclicEF(LinFixedEF):
    """Cyclic EF (Entry File) in the smart card filesystem"""
    # we don't really have any special support for those; just recycling LinFixedEF here
    def __init__(self, fid, sfid=None, name=None, desc=None, parent=None, rec_len={1,None}):
        super().__init__(fid, sfid, name, desc, parent, rec_len)

class TransRecEF(TransparentEF):
    """Transparent EF (Entry File) containing fixed-size records.
    These are the real odd-balls and mostly look like mistakes in the specification:
    Specified as 'transparent' EF, but actually containing several fixed-length records
    inside.
    We add a special class for those, so the user only has to provide encoder/decoder functions
    for a record, while this class takes care of split / merge of records.
    """
    def __init__(self, fid, sfid=None, name=None, desc=None, parent=None, rec_len=None, size={1,None}):
        super().__init__(fid, sfid, name, desc, parent, size)
        self.rec_len = rec_len

    def decode_record_hex(self, raw_hex_data):
        """Decode raw (hex string) data into abstract representation. Overloaded by specific classes."""
        method = getattr(self, '_decode_record_hex')
        if callable(method):
            return method(raw_hex_data)
        method = getattr(self, '_decode_record_bin')
        if callable(method):
            return method(h2b(raw_hex_data))
        return {'raw': h2b(raw_hex_data)}

    def decode_record_bin(self, raw_bin_data):
        """Decode raw (hex string) data into abstract representation. Overloaded by specific classes."""
        method = getattr(self, '_decode_record_bin')
        if callable(method):
            return method(raw_bin_data)
        method = getattr(self, '_decode_record_hex')
        if callable(method):
            return method(b2h(raw_bin_data))
        return {'raw': raw_bin_data}

    def encode_record_hex(self, abstract_data):
        """Encode abstract representation into raw (hex string) data. Overloaded by specific classes."""
        method = getattr(self, '_encode_record_hex')
        if callable(method):
            return method(abstract_data)
        method = getattr(self, '_encode_record_bin')
        if callable(method):
            return h2b(method(abstract_data))
        raise NotImplementedError

    def encode_record_bin(self, abstract_data):
        """Encode abstract representation into raw (binary) data. Overloaded by specific classes."""
        method = getattr(self, '_encode_record_bin')
        if callable(method):
            return method(abstract_data)
        method = getattr(self, '_encode_record_hex')
        if callable(method):
            return h2b(method(abstract_data))
        raise NotImplementedError

    def _decode_bin(self, raw_bin_data):
        chunks = [raw_bin_data[i:i+self.rec_len] for i in range(0, len(raw_bin_data), self.rec_len)]
        return [self.decode_record_bin(x) for x in chunks]

    def _encode_bin(self, abstract_data):
        chunks = [self.encode_record_bin(x) for x in abstract_data]
# FIXME: pad to file size
        return b''.join(chunks)





class RuntimeState(object):
    """Represent the runtime state of a session with a card."""
    def __init__(self, mf, card):
        self.card = card
        self.mf = mf
        self.selected_file = self.mf

    def get_cwd(self):
        if isinstance(self.selected_file, DF):
            return self.selected_file
        else:
            return self.selected_file.parent

    def select(self, name, cmd_app=None):
        """Change current directory"""
        sels = self.selected_file.get_selectables()
        if name in sels:
            f = sels[name]
            # unregister commands of old file
            if cmd_app and self.selected_file.shell_commands:
                for c in self.selected_file.shell_commands:
                    cmd_app.unregister_command_set(c)
            if isinstance(f, ADF):
                self.card._scc.select_adf(f.aid)
            else:
                self.card._scc.select_file(f.fid)
            self.selected_file = f
            # register commands of new file
            if cmd_app and self.selected_file.shell_commands:
                for c in self.selected_file.shell_commands:
                    cmd_app.register_command_set(c)
        #elif looks_like_fid(name):
        else:
            raise ValueError("Cannot select unknown %s" % (name))

    def read_binary(self, length=None, offset=0):
        if not isinstance(self.selected_file, TransparentEF):
            raise TypeError("Only works with TransparentEF")
        return self.card._scc.read_binary(self.selected_file.fid, length, offset)

    def read_binary_dec(self):
        (data, sw) = self.read_binary()
        return (self.selected_file.decode_hex(data), sw)

    def update_binary(self, data_hex, offset=0):
        if not isinstance(self.selected_file, TransparentEF):
            raise TypeError("Only works with TransparentEF")
        return self.card._scc.update_binary(self.selected_file.fid, data_hex, offset)

    def update_binary_dec(self, data):
        hex_data = self.selected_file.encode_hex(data)
        return self.update_binary(data_hex)

    def read_record(self, rec_nr=0):
        if not isinstance(self.selected_file, LinFixedEF):
            raise TypeError("Only works with Linear Fixed EF")
        return self.card._scc.read_record(self.selected_file.fid, rec_nr)

    def read_record_dec(self, rec_nr=0):
        (data, sw) = self.read_record(rec_nr)
        return (self.selected_file.decode_record_hex(data), sw)

    def update_record(self, rec_nr, data_hex):
        if not isinstance(self.selected_file, LinFixedEF):
            raise TypeError("Only works with Linear Fixed EF")
        return self.card._scc.update_record(self.selected_file.fid, rec_nr, data_hex)

    def update_record_dec(self, rec_nr, data):
        hex_data = self.selected_file.encode_record_hex(data)
        return self.update_record(self, rec_nr, data_hex)



class FileData(object):
    """Represent the runtime, on-card data."""
    def __init__(self, fdesc):
        self.desc = fdesc
        self.fcp = None

######################################################################

if __name__ == '__main__':
    mf = MF()

    adf_usim = ADF('a0000000871002', name='ADF_USIM')
    mf.add_application(adf_usim)
    df_pb = DF('5f3a', name='DF.PHONEBOOK')
    adf_usim.add_file(df_pb)
    adf_usim.add_file(TransparentEF('6f05', name='EF.LI', size={2,16}))
    adf_usim.add_file(TransparentEF('6f07', name='EF.IMSI', size={9,9}))

    rss = RuntimeState(mf, None)

    interp = code.InteractiveConsole(locals={'mf':mf, 'rss':rss})
    interp.interact()

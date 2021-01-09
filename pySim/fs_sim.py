# coding=utf-8
"""Representation of the GSM SIM/USIM/ISIM filesystem hierarchy.

The File (and its derived classes) uses the classes of pySim.filesystem in
order to describe the files specified in the relevant ETSI + 3GPP specifications.

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

from pySim.utils import *
from pySim.ts_51_011 import *
from struct import pack, unpack

from pySim.filesystem import *

######################################################################
# DF.TELECOM
######################################################################

# TS 51.011 Section 10.5.1
class EF_ADN(LinFixedEF):
    def __init__(self, fid='6f3a', sfid=None, name='EF.ADN', desc='Abbreviated Dialing Numbers'):
        super().__init__(fid, sfid=sfid, name=name, desc=desc, rec_len={14, 30})
    def _decode_record_bin(self, raw_bin_data):
        alpha_id_len = len(raw_bin_data) - 14
        alpha_id = raw_bin_data[:alpha_id_len]
        u = unpack('!BB10sBB', raw_bin_data[-14:])
        return {'alpha_id': alpha_id, 'len_of_bcd': u[0], 'ton_npi': u[1],
                'dialing_nr': u[2], 'cap_conf_id': u[3], 'ext1_record_id': u[4]}

# TS 51.011 Section 10.5.5
class EF_MSISDN(LinFixedEF):
    def __init__(self, fid='6f4f', sfid=None, name='EF.MSISDN', desc='MSISDN'):
        super().__init__(fid, sfid=sfid, name=name, desc=desc, rec_len={15, None})
    def _decode_record_hex(self, raw_hex_data):
        return {'msisdn': dec_msisdn(raw_hex_data)}
    def _encode_record_hex(self, abstract):
        return enc_msisdn(abstract['msisdn'])

# TS 51.011 Section 10.5.6
class EF_SMSP(LinFixedEF):
    def __init__(self, fid='6f42', sfid=None, name='EF.SMSP', desc='Short message service parameters'):
        super().__init__(fid, sfid=sfid, name=name, desc=desc, rec_len={28, None})

class DF_TELECOM(DF):
    def __init__(self, fid='7f10', name='DF.TELECOM', desc=None):
        super().__init__(fid, name=name, desc=desc)
        files = [
          EF_ADN(),
          EF_MSISDN(),
          EF_SMSP(),
          ]


######################################################################
# DF.GSM
######################################################################

# TS 51.011 Section 10.3.2
class EF_IMSI(TransparentEF):
    def __init__(self, fid='6f07', sfid=None, name='EF.IMSI', desc='IMSI', size={9,9}):
        super().__init__(fid, sfid=sfid, name=name, desc=desc, size=size)
    def _decode_hex(self, raw_hex):
        return {'imsi': dec_imsi(raw_hex)}
    def _encode_hex(self, abstract):
        return enc_imsi(abstract['imsi'])

# TS 51.011 Section 10.3.4
class EF_PLMNsel(TransRecEF):
    def __init__(self, fid='6f30', sfid=None, name='EF.PLMNsel', desc='PLMN selector',
                 size={24,None}, rec_len=3):
        super().__init__(fid, name=name, sfid=sfid, desc=desc, size=size, rec_len=rec_len)

# TS 51.011 Section 10.3.7
class EF_ServiceTable(TransparentEF):
    def __init__(self, fid, sfid, name, desc, size, table):
        super().__init__(fid, sfid=sfid, name=name, desc=desc, size=size)
        self.table = table
    def _decode_bin(self, raw_bin):
        ret = []
        for i in range(0, len(raw_bin)*4):
            service_nr = i+1
            byte = int(raw_bin[i/4])
            bit_offset = (i % 4) * 2
            bits = (byte >> bit_offset) & 3
            ret.add({'number': service_nr,
                     'description': table[service_nr] or None,
                     'allocated': bits & 1,
                     'activated': bits & 2,
                     })

# TS 51.011 Section 10.3.11
class EF_SPN(TransparentEF):
    def __init__(self, fid='6f46', sfid=None, name='EF.SPN', desc='Service Provider Name', size={17,17}):
        super().__init__(fid, sfid=sfid, name=name, desc=desc, size=size)
    def _decode_hex(self, raw_hex):
        return {'spn': dec_spn(raw_hex)}
    def _encode_hex(self, abstract):
        return enc_spn(abstract['spn'])

# TS 51.011 Section 10.3.13
class EF_CBMI(TransRecEF):
    def __init__(self, fid='6f45', sfid=None, name='EF.CBMI', size={2,None}, rec_len=2,
                 desc='Cell Broadcast message identifier selection'):
        super().__init__(fid, sfid=sfid, name=name, desc=desc, size=size, rec_len=rec_len)

# TS 51.011 Section 10.3.15
class EF_ACC(TransparentEF):
    def __init__(self, fid='6f78', sfid=None, name='EF.ACC', desc='Access Control Class', size={2,2}):
        super().__init__(fid, sfid=sfid, name=name, desc=desc, size=size)
    def _decode_bin(self, raw_bin):
        return {'acc': unpack('!H', raw_bin)[0]}
    def _encode_bin(self, abstract):
        return pack('!H', abstract['acc'])

# TS 51.011 Section 10.3.18
class EF_AD(TransparentEF):
    OP_MODE = {
            0x00: 'normal operation',
            0x80: 'type approval operations',
            0x01: 'normal operation + specific facilities',
            0x81: 'type approval + specific facilities',
            0x02: 'maintenance (off line)',
            0x04: 'cell test operation',
        }
    def __init__(self, fid='6fad', sfid=None, name='EF.AD', desc='Administrative Data', size={3,4}):
        super().__init__(fid, sfid=sfid, name=name, desc=desc, size=size)
    def _decode_bin(self, raw_bin):
        u = unpack('!BH', raw_bin[:3])

# TS 51.011 Section 10.3.13
class EF_CBMID(EF_CBMI):
    def __init__(self, fid='6f48', sfid=None, name='EF.CBMID', size={2,None}, rec_len=2,
                 desc='Cell Broadcast Message Identifier for Data Download'):
        super().__init__(fid, sfid=sfid, name=name, desc=desc, size=size, rec_len=rec_len)

# TS 51.011 Section 10.3.26
class EF_ECC(LinFixedEF):
    def __init__(self, fid='6fb7', sfid=None, name='EF.ECC', desc='Emergency Call Codes'):
        super().__init__(fid, sfid=sfid, name=name, desc=desc, rec_len={4, 20})

# TS 51.011 Section 10.3.28
class EF_CBMIR(TransRecEF):
    def __init__(self, fid='6f50', sfid=None, name='EF.CBMIR', size={4,None}, rec_len=4,
                 desc='Cell Broadcast message identifier range selection'):
        super().__init__(fid, sfid=sfid, name=name, desc=desc, size=size, rec_len=rec_len)


# TS 51.011 Section 10.3.35..37
class EF_xPLMNwAcT(TransRecEF):
    def __init__(self, fid, sfid=None, name=None, desc=None, size={40,None}, rec_len=5):
        super().__init__(fid, sfid=sfid, name=name, desc=desc, size=size, rec_len=rec_len)

class DF_GSM(DF):
    def __init__(self, fid='7f20', name='DF.GSM', desc='GSM Network related files'):
        super().__init__(fid, name=name, desc=desc)
        files = [
          TransRecEF('6f05', None, 'EF.LP', 'Language preference', size={1,None}, rec_len=1),
          EF_IMSI(),
          TransparentEF('5f20', None, 'EF.Kc', 'Ciphering key Kc'),
          EF_PLMNsel(),
          TransparentEF('6f31', None, 'EF.HPPLMN', 'Higher Priprity PLMN search period'),
          EF_ServiceTable('6f37', None, 'EF.SST', 'SIM service table', table=EF_SST_map, size={2,16}),
          CyclicEF('6f39', None, 'EF.ACM', 'Accumulated call meter', rec_len={4,3}),
          TransparentEF('6f3e', None, 'EF.GID1', 'Group Identifier Level 1'),
          TransparentEF('6f3f', None, 'EF.GID2', 'Group Identifier Level 2'),
          EF_SPN(),
          TransparentEF('6f41', None, 'EF.PUCT', 'Price per unit and currency table', size={5,5}),
          EF_CBMI(),
          TransparentEF('6f7f', None, 'EF.BCCH', 'Broadcast control channels', size={16,16}),
          EF_ACC(),
          EF_PLMNsel('6f7b', None, 'EF.FPLMN', 'Forbidden PLMNs', size={12,12}),
          TransparentEF('6f7e', None, 'EF.LOCI', 'Locationn information', size={11,11}),
          TransparentEF('6fa3', None, 'EF.Phase', 'Phase identification', size={1,1}),
        # TODO EF.VGCS ...
          EF_CBMID(),
          EF_ECC(),
          EF_CBMIR(),
          EF_AD(),
          EF_xPLMNwAcT('6f60', None, 'EF.PLMNwAcT',
                                   'User controlled PLMN Selector with Access Technology'),
          EF_xPLMNwAcT('6f61', None, 'EF.OPLMNwAcT',
                                   'Operator controlled PLMN Selector with Access Technology'),
          EF_xPLMNwAcT('6f62', None, 'EF.HPLMNwAcT', 'HPLMN Selector with Access Technology'),
          ]
        self.add_files(files)

######################################################################
# ADF.USIM
######################################################################

class EF_LI(TransRecEF):
    def __init__(self, fid='6f05', sfid=None, name='EF.LI', size={2,None}, rec_len=2,
                 desc='Language Indication'):
        super().__init__(fid, sfid=sfid, name=name, desc=desc, size=size, rec_len=rec_len)

class ADF_USIM(ADF):
    def __init__(self, aid='a0000000871002', name='ADF.USIM', fid=None, sfid=None,
                 desc='USIM Application'):
        super().__init__(aid=aid, fid=fid, sfid=sfid, name=name, desc=desc)
        self.shell_commands += [self.ShellCommands()]

        files = [
          EF_LI(sfid=0x02),
          EF_IMSI(sfid=0x07),
          TransparentEF('6f08', 0x08, 'EF.Keys', size={33,33}, desc='Ciphering and Integrity Keys'),
          TransparentEF('6f09', 0x09, 'EF.KeysPS', size={33,33},
                        desc='Ciphering and Integrity Keys for PS domain'),
          EF_xPLMNwAcT('6f60', 0x0a, 'EF.PLMNwAcT',
                       'User controlled PLMN Selector with Access Technology'),
          TransparentEF('6f31', 0x12, 'EF.HPPLMN', 'Higher Priprity PLMN search period'),
          # EF.ACMmax
          # EF.UST
          # EF.ACM
          CyclicEF('6f39', None, 'EF.ACM', 'Accumulated call meter', rec_len={3,3}),
          TransparentEF('6f3e', None, 'EF.GID1', 'Group Identifier Level 1'),
          TransparentEF('6f3f', None, 'EF.GID2', 'Group Identifier Level 2'),
          EF_SPN(),
          TransparentEF('6f41', None, 'EF.PUCT', 'Price per unit and currency table', size={5,5}),
          EF_CBMI(),
          EF_ACC(sfid=0x06),
          EF_PLMNsel('6f7b', 0x0d, 'EF.FPLMN', 'Forbidden PLMNs', size={12,None}),
          TransparentEF('6f7e', 0x0b, 'EF.LOCI', 'Locationn information', size={11,11}),
          EF_AD(sfid=0x03),
          EF_CBMID(sfid=0x0e),
          EF_ECC(sfid=0x01),
          EF_CBMIR(),
          ]
        self.add_files(files)


    @with_default_category('File-Specific Commands')
    class ShellCommands(CommandSet):
        def __init__(self):
            super().__init__()

        def do_ust_service_activate(self, arg):
            """Activate a service within EF.UST"""
            self._cmd.card.update_ust(int(arg), 1)

        def do_ust_service_deactivate(self, arg):
            """Deactivate a service within EF.UST"""
            self._cmd.card.update_ust(int(arg), 0)

#!/usr/bin/env python3

import cmd2
from cmd2 import style, fg, bg
from cmd2 import CommandSet, with_default_category, with_argparser
import argparse

import os
import sys
from optparse import OptionParser

from pySim.ts_51_011 import EF, DF, EF_SST_map, EF_AD_mode_map
from pySim.ts_31_102 import EF_UST_map, EF_USIM_ADF_map
from pySim.ts_31_103 import EF_IST_map, EF_ISIM_ADF_map

from pySim.commands import SimCardCommands
from pySim.cards import card_detect, Card
from pySim.utils import h2b, swap_nibbles, rpad, h2s
from pySim.utils import dec_st, init_reader, sanitize_pin_adm
from pySim.card_handler import card_handler

class PysimApp(cmd2.Cmd):
	CUSTOM_CATEGORY = 'pySim Commands'
	def __init__(self, card):
		#super().__init__(persistent_history_file='~/.pysim_shell_history', allow_cli_args=False)
		super().__init__(persistent_history_file='~/.pysim_shell_history', allow_cli_args=False,
				use_ipython=True)
		self.intro = style('Welcome to pySim-shell!', fg=fg.red)
		self.default_category = 'pySim-shell built-in commands'
		self.card = card
		self.path = ['3f00']
		self.update_prompt()
		self.py_locals = { 'card': self.card, 'path' : self.path }
		self.card.read_aids()
		self.poutput('AIDs on card: %s' % (self.card._aids))

	def update_prompt(self):
		self.prompt = 'pySIM-shell (%s)> ' % ('/'.join(self.path))

	def update_path(self, path):
		for p in path:
			if p == '3f00':
				self.path = []
			self.path.append(p)
		self.update_prompt()

	def set_path(self, path):
		self.path = path
		self.update_prompt()

	@cmd2.with_category(CUSTOM_CATEGORY)
	def do_intro(self, _):
		"""Display the intro banner"""
		self.poutput(self.intro)

	@cmd2.with_category(CUSTOM_CATEGORY)
	def do_verify_adm(self, arg):
		"""VERIFY the ADM1 PIN"""
		pin_adm = sanitize_pin_adm(arg)
		self.card.verify_adm(h2b(pin_adm))



@with_default_category('ISO7816 Commands')
class Iso7816Commands(CommandSet):
	def __init__(self):
		super().__init__()

	def do_select_file(self, opts):
		"""SELECT a DF (Dedicated File) or EF (Entry File)"""
		path = opts.arg_list
		rv = self._cmd.card._scc.select_file(path)
		self._cmd.poutput(rv)
		# TODO: check if it was a DF or EF and update path accordingly
		self._cmd.update_path(path)

	def do_select_adf(self, opts):
		"""SELECT an ADF (Application Dedicated File)"""
		aid = opts.arg_list[0]
		rv = self._cmd.card._scc.select_adf(aid)
		self._cmd.poutput(rv)
		self._cmd.set_path([aid])

	read_bin_parser = argparse.ArgumentParser()
	rbpg = read_bin_parser.add_mutually_exclusive_group()
	rbpg.add_argument('--file-id', help='File ID')
	#rbpg.add_argument('--sfid', help='Short File ID')
	read_bin_parser.add_argument('--offset', type=int, default=0, help='Byte offset for start of read')
	read_bin_parser.add_argument('--length', type=int, help='Number of bytes to read')

	@cmd2.with_argparser(read_bin_parser)
	def do_read_binary(self, opts):
		"""Read binary data from a transparent EF"""
		(data, sw) = self._cmd.card._scc.read_binary(opts.file_id, opts.length, opts.offset)
		self._cmd.poutput(data)

	upd_bin_parser = argparse.ArgumentParser()
	ubpg = upd_bin_parser.add_mutually_exclusive_group()
	ubpg.add_argument('--file-id', help='File ID')
	#ubpg.add_argument('--sfid', help='Short File ID')
	upd_bin_parser.add_argument('--offset', type=int, default=0, help='Byte offset for start of read')
	upd_bin_parser.add_argument('data', help='Data bytes (hex format) to write')

	@cmd2.with_argparser(upd_bin_parser)
	def do_update_binary(self, opts):
		"""Update (Write) data of a transparent EF"""
		(data, sw) = self._cmd.card._scc.update_binary(opts.file_id, opts.data, opts.offset)
		self._cmd.poutput(data)

	read_rec_parser = argparse.ArgumentParser()
	rrpg = read_rec_parser.add_mutually_exclusive_group()
	rrpg.add_argument('--file-id', help='File ID')
	#rrpg.add_argument('--sfid', help='Short File ID')
	read_bin_parser.add_argument('--record-nr', type=int, default=0, help='Number of record to read')

	@cmd2.with_argparser(read_rec_parser)
	def du_read_record(self, opts):
		"""Read a record from a record-oriented EF"""
		(data, sw) = self._cmd.card._scc.read_record(opts.file_id, opts.record_nr)
		self._cmd.poutput(data)

	upd_rec_parser = argparse.ArgumentParser()
	urpg = upd_rec_parser.add_mutually_exclusive_group()
	urpg.add_argument('--file-id', help='File ID')
	#urpg.add_argument('--sfid', help='Short File ID')
	upd_rec_parser.add_argument('--record-nr', type=int, default=0, help='Number of record to read')
	upd_rec_parser.add_argument('data', help='Data bytes (hex format) to write')

	@cmd2.with_argparser(upd_rec_parser)
	def do_update_record(self, opts):
		"""Update (write) data to a record-oriented EF"""
		(data, sw) = self._cmd.card._scc.update_record(opts.file_id, opts.record_nr, opts.data)
		self._cmd.poutput(data)

	verify_chv_parser = argparse.ArgumentParser()
	verify_chv_parser.add_argument('--chv-nr', type=int, default=1, help='CHV Number')
	verify_chv_parser.add_argument('code', help='CODE/PIN/PUK')

	@cmd2.with_argparser(verify_chv_parser)
	def do_verify_chv(self, opts):
		"""Verify (authenticate) using specified CHV (PIN)"""
		(data, sw) = self._cmd.card._scc.verify_chv(opts.chv_nr, opts.code)
		self._cmd.poutput(data)




@with_default_category('USIM Commands')
class UsimCommands(CommandSet):
	def __init__(self):
		super().__init__()

	def do_ust_service_activate(self, arg):
		"""Activate a service within EF.UST"""
		self._cmd.card.select_adf_by_aid(adf="usim")
		self._cmd.card.update_ust(int(arg), 1);

	def do_ust_service_deactivate(self, arg):
		"""Deactivate a service within EF.UST"""
		self._cmd.card.select_adf_by_aid(adf="usim")
		self._cmd.card.update_ust(int(arg), 0);

	def do_read_ust(self, _):
		"""Read + Display the EF.UST"""
		self._cmd.card.select_adf_by_aid(adf="usim")
		(res, sw) = self._cmd.card.read_ust()
		self._cmd.poutput(res[0])
		self._cmd.poutput(res[1])

	def do_read_ehplmn(self, _):
		"""Read EF.EHPLMN"""
		self._cmd.card.select_adf_by_aid(adf="usim")
		(res, sw) = self._cmd.card.read_ehplmn()
		self._cmd.poutput(res)

def parse_options():

	parser = OptionParser(usage="usage: %prog [options]")

	parser.add_option("-d", "--device", dest="device", metavar="DEV",
			help="Serial Device for SIM access [default: %default]",
			default="/dev/ttyUSB0",
		)
	parser.add_option("-b", "--baud", dest="baudrate", type="int", metavar="BAUD",
			help="Baudrate used for SIM access [default: %default]",
			default=9600,
		)
	parser.add_option("-p", "--pcsc-device", dest="pcsc_dev", type='int', metavar="PCSC",
			help="Which PC/SC reader number for SIM access",
			default=None,
		)
	parser.add_option("--modem-device", dest="modem_dev", metavar="DEV",
			help="Serial port of modem for Generic SIM Access (3GPP TS 27.007)",
			default=None,
		)
	parser.add_option("--modem-baud", dest="modem_baud", type="int", metavar="BAUD",
			help="Baudrate used for modem's port [default: %default]",
			default=115200,
		)
	parser.add_option("--osmocon", dest="osmocon_sock", metavar="PATH",
			help="Socket path for Calypso (e.g. Motorola C1XX) based reader (via OsmocomBB)",
			default=None,
		)

	parser.add_option("-a", "--pin-adm", dest="pin_adm",
			help="ADM PIN used for provisioning (overwrites default)",
		)
	parser.add_option("-A", "--pin-adm-hex", dest="pin_adm_hex",
			help="ADM PIN used for provisioning, as hex string (16 characters long",
		)

	(options, args) = parser.parse_args()

	if args:
		parser.error("Extraneous arguments")

	return options



if __name__ == '__main__':

	# Parse options
	opts = parse_options()

	# Init card reader driver
	sl = init_reader(opts)

	# Create command layer
	scc = SimCardCommands(transport=sl)

	sl.wait_for_card();

	card_handler = card_handler(sl)

	card = card_detect("auto", scc)
	if card is None:
		print("No card detected!")
		sys.exit(2)

	app = PysimApp(card)
	app.cmdloop()

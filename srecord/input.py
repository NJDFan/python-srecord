"""
Input classes are used to read files from disk into SparseData
structures.  Input classes will all support the use of a filename in 
the initializer, which if present will call the read() method to
read the file data in.  read returns self.data for convenience, but
this value can be ignored and used independently.

The bulk of the data in will be returned in a SparseData structure
stored as instance.data, but non-trivial input classes may have other
members for other data, such as header strings, execution start
addresses, etc.

"""

import re

from .core import *
from . import settings

##############################################################################
# Utility classes/functions

class InvalidRecord(Exception):
	pass
	
def _read_big_endian(data):
	"""Read a bytearray as one big-endian number."""
	total = 0
	for d in data:
		total = (total * 256) + d
	return total
	
class _SrecordDataInput(object):
	def __init__(self, filename=None):
		"""
		Create a new input reader.
		
		If filename is given, immediately call read on it.
		"""
		self._data = None
		
		if filename:
			self.read(filename)
		
	def read(self, filename):
		"""Read in and parse the source file.""" 
		raise NotImplementedError
		
	@property
	def data(self):
		"""A SparseData object representing all data from this file."""
		return self._data
		
##############################################################################
# Publicly available input classes.

class BinaryInput(_SrecordDataInput):
	"""Represents a file to be brought in as straight binary."""
	def read(self, filename):
		"""All file data will be one chunk, starting at address 0."""
		with open(filename, 'rb') as f:
			self._data = SparseData(DataChunk(0, f.read()))
		return self._data

class SrecInput(_SrecordDataInput):
	"""Represents a Motorola SREC file."""
	
	srecord = re.compile(r"""
		S
		([01235789])
		([0-9A-F]{2})
		([0-9A-F]+)
		([0-9A-F]{2})
		$
		""", re.VERBOSE)
	
	def _resetStates(self):
		self._header = []
		self._startAddress = None
		
	@property
	def header(self):
		"""A list of header information collected from S0 records."""
		return self._header
	
	@property
	def startAddress(self):
		"""The execution start address from an S7-9 record."""
		return self._startAddress
	
	def __init__(self, filename=None,
					force_good_checksum=True,
					force_good_bytecount=True,
					force_valid_recordcount=True,
					force_all_records=False
					):
		self._force_good_checksum = force_good_checksum
		self._force_good_bytecount = force_good_bytecount
		self._force_valid_recordcount = force_valid_recordcount
		self._force_all_records = force_all_records
		
		self._resetStates()
		super(SrecInput, self).__init__(filename)
		
	def read(self, filename):
		"""Read and parse any S19, S28, or S37 file."""
		# Reinitialize
		self._resetStates()
		self._data = SparseData()
		record_count = 0
		
		# And rip the file
		with open(filename, 'r') as f:
			for (ln, line) in enumerate(f):
				# Initial line parsing
				
				mo = re.match("S([0-357-9])([0-9A-F]{2})([0-9A-F]+)([0-9A-F]{2})$", line.upper().strip())
				if not mo:
					# This isn't even an srecord
					if self._force_all_records:
						raise InvalidRecord("Not an S-record.", ln)
					else:
						continue
			
				# Data type translation
				S, bytecount, blockdata, checksum = mo.groups()
				S = int(S)
				bytecount = int(bytecount, 16) - 1
				blockdata = bytearray( int(blockdata[i:i+2], 16) for i in range(0, len(blockdata), 2) )
				checksum = int(checksum, 16)
				
				# Record validation: bytecount and checksum
				if self._force_good_bytecount and len(blockdata) != bytecount:
					raise InvalidRecord("Bad bytecount.", ln)
					
				if self._force_good_checksum:
					block_checksum = (~sum(blockdata, bytecount + 1)) & 0xFF
					if checksum != block_checksum:
						raise InvalidRecord(
							"Checksum failed: {0:02X} instead of {1:02X}.".format(block_checksum, checksum),
							 ln
						)
					
				# Alright, having validated the checksum, let's do something
				# with the data.
				if S == 0:
					# Block header.  Ignore the two address bytes
					self._header.append(blockdata[2:])
					
				elif S in (1, 2, 3):
					# Data record; separate the address from the data
					record_count += 1
					
					# Get the address (big-endian), and slap the data record in
					address_bytes = S + 1
					address = _read_big_endian(blockdata[0:address_bytes])
					self._data.add(DataChunk(address, blockdata[address_bytes:]))
					
				elif S == 5:	
					# Record count.  If we have one, it should match.
					# The block data is all count.
					if self._force_valid_recordcount:
						count = _read_big_endian(blockdata)
						if count != record_count:
							raise InvalidRecord("Bad record count.", ln)
							
				elif S in (7, 8, 9):
					self._startAddress = _read_big_endian(blockdata)

		return self._data

class HexInput(_SrecordDataInput):
	"""Represents an Intel hex file.
	
	Reference: https://en.wikipedia.org/w/index.php?title=Intel_HEX&oldid=1091252493
	"""
	
	def _resetStates(self):
		self._baseaddr = 0
		self._eof = False
	
	def __init__(self, filename=None,
					force_good_checksum=True,
					force_good_bytecount=True,
					eof_error=True
					):
		self._force_good_checksum = force_good_checksum
		self._force_good_bytecount = force_good_bytecount
		self._eof_error = eof_error
		
		self._resetStates()
		super().__init__(filename)
	
	# Parser table
	def _recorddata(self, rec):
		addr = self._baseaddr + rec['addr']
		self._data.add(DataChunk(addr, rec['data']))
	
	def _recordeof(self, rec):
		self._eof = True
	
	def _recordsegaddr(self, rec):
		if rec['dlen'] != 2:
			raise InvalidRecord('segment address has data len {}, should be 2'.format(rec['dlen']))
			
		d = rec['data']
		self._baseaddr = (d[0] << 12) | (d[1] << 4)
		
	def _recordstartseg(self, rec):
		if rec['dlen'] != 4:
			raise InvalidRecord('start segment has data len {}, should be 4'.format(rec['dlen']))
		
		d = rec['data']
		self.startcs = (d[0] << 8) | d[1]
		self.startpc = (d[2] << 8) | d[3]
		
	def _recordlinaddr(self, rec):
		if rec['dlen'] != 2:
			raise InvalidRecord('segment address has data len {}, should be 2'.format(rec['dlen']))
			
		d = rec['data']
		self._baseaddr = (d[0] << 24) | (d[1] << 16)
		
	def _recordstartlin(self, rec):
		if rec['dlen'] != 4:
			raise InvalidRecord('start segment has data len {}, should be 4'.format(rec['dlen']))
		
		d = rec['data']
		self.startpc = (d[0] << 24) | (d[1] << 16) | (d[2] << 8) | d[3]
	
	def read(self, filename):
		self._resetStates()
		self._data = SparseData()
		# Linebreaks are nice but not necessary in HEX format, so ignore them.
		# Slurp the entire file, nuke the whitespace, and break it on the
		# : record separator character.
		with open(filename) as f:
			data = re.sub(r'\s', '', f.read(), flags=re.MULTILINE)
		
		# Use the rec['type'] field to form a dispatch to the various
		# parsing functions.
		recparse = {
			0 : self._recorddata,
			1 : self._recordeof,
			2 : self._recordsegaddr,
			3 : self._recordstartseg,
			4 : self._recordlinaddr,
			5 : self._recordstartlin
		}
		
		for record in data.split(':'):
			if not record:
				continue
				
			if self._eof_error and self._eof:
				raise InvalidRecord('data past EOF record')
			
			b = bytes.fromhex(record)
			rec = {
				'dlen' : b[0],
				'addr' : (b[1] << 8) | b[2],
				'type' : b[3],
				'data' : b[4:-1],
				'cksm' : b[-1]
			}
			if self._force_good_checksum:
				checksum = sum(b) & 0xFF
				if checksum:
					raise InvalidRecord('bad checksum')
			
			if self._force_good_bytecount:
				if len(rec['data']) != rec['dlen']:
					raise InvalidRecord('bad data length')
					
			recparse[rec['type']](rec)
			
		return self._data

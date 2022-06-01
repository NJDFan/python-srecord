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

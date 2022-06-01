"""
Output classes are used to write data out to disk.

The basic call will be

	output.OutputClass(sdata, filename [, optional keyword arguments)
	
This can also be done in two stages if desired.

	output.OutputClass(sdata [, optional keyword arguments])
	output.write(filename)

"""

import itertools
import struct

from .core import *
from . import settings

class _SrecordDataOutput(object):
	def __init__(self, sdata, filename=None):
		"""
		Create a new output writer.
		
		If filename is given, immediately call write on it.
		"""
		self.sdata = sdata
		
		if filename:
			self.write(filename)
		
	def write(self, filename):
		"""Write the data out to the target file.""" 
		raise NotImplementedError
		
class BinaryOutput(_SrecordDataOutput):
	"""
	Represents a file to be written out as straight binary.

	Because straight binary files don't support address information,
	we'll only allow the writing of SparseData that consists of only
	one contiguous region.  Use generators to fill gaps as needed.
	
	"""
	def write(self, filename):
		if len(self.sdata) > 1:
			raise NonContiguousError("Can't write binary file from multiple regions.")
			
		with open(filename, 'wb') as f:
			f.write(self.sdata[0])

class SrecOutput(_SrecordDataOutput):
	"""
	Represents a file to written out as S-record data.
	"""
	
	def __init__(self, sdata, filename=None,
					address_bytes=None,
					header=None,
					start_address=None,
					bytes_per_line=32
					):
						
		if address_bytes is None:
			if sdata.end() <= 0xFFFF:
				self.address_bytes = 2
			elif sdata.end() <= 0xFFFFFF:
				self.address_bytes = 3
			else:
				self.address_bytes = 4
		elif address_bytes in (2, 3, 4):
			self.address_bytes = address_bytes
			
		else:
			raise ValueError("address_bytes must be 2-4, or None to autosize")
			
		if header is None:
			self.header = []
		else:
			self.header = header
		self.start_address = start_address
		self.bytes_per_line = bytes_per_line
						
		super(SrecOutput, self).__init__(sdata, filename)
		
	def _make_bigendian(self, x):
		"""
		Generate a bytearray holding integer x as a
		big-endian number.
		
		The array will be self.address_bytes long. 
		
		"""
		a = bytearray(self.address_bytes)
		pos = len(a)-1
		while x > 0:
			a[pos] = x & 0xFF
			pos -= 1
			x >>= 8
		return a
						
	def _make_srec(self, data):
		d = bytearray(data)
		data_len = len(d) + 1
		checksum = ~sum(d, data_len) & 0xFF
		return ''.join('{0:02X}'.format(x) for x in itertools.chain(
							[data_len],
							d,
							[checksum]
						))
						
	def write(self, filename):
		# Validate the address lengths
		if self.address_bytes not in (2, 3, 4):
			raise ValueError("address_bytes must be 2-4.")

		if self.sdata.end() > (256**self.address_bytes):
			raise ValueError(
				"{0} address_bytes insufficient for the data.".format(self.address_bytes)
			)

		# And actually write out the file
		with open(filename, 'w') as f:
			# Start with header records
			for (addr, rec) in enumerate(self.header):
				print("S0" + self._make_srec(
								struct.pack(">H", addr) +
								bytearray(rec)
							), file=f)
				
			# Now data records
			stype = "S{0}".format(self.address_bytes - 1)
			for chunk in self.sdata:
				addr = chunk.start()
				for data in iterate_count(iter(chunk), self.bytes_per_line):
					a = self._make_bigendian(addr)
					addr += len(data)
					print(stype + self._make_srec(a + bytearray(data)), file=f)
					
			# Finally, any execution start stuff.
			if self.start_address is not None:
				stype = "S{0}".format(9 + 2 - self.address_bytes)
				a = self._make_bigendian(self.start_address)
				print(stype + self._make_srec(a), file=f)
					

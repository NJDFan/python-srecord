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
	def __init__(self, sdata:SparseData, filename:str=None):
		"""
		Create a new output writer.
		
		If filename is given, immediately call write on it.
		"""
		self.sdata = sdata
		
		if filename:
			self.write(filename)
		
	def write(self, filename:str):
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
	
	Args:
		sdata: The data to be written to the S-record file.
		
		filename: Shortcut to immediately call write() against this file.
		
		header: If provided, can be either a string, bytes or a dict containing
			string 'mname', 'ver', 'rev', and optional 'description' fields.
			Generates an S0 header field.
			
		address_bytes: 2-4 to specify the number of bytes in address fields.
			If None, autodetects based on highest address needed for sdata.
			
		start_address: If provided, adds an execution start address record
			(S7-9) into the S-record file.
			
		bytes_per_line: Maximum number of data bytes per line.
	
	"""
	
	def __init__(self, sdata:SparseData, filename:str=None,
					address_bytes:int=None,
					header=None,
					start_address:int=None,
					bytes_per_line:int=32
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
			self.header = None
		elif isinstance(header, (bytes, bytearray)):
			self.header = header
		elif isinstance(header, str):
			self.header = header.encode()
		elif isinstance(header, dict):
			knownkeys = ('mname', 'ver', 'rev', 'description')
			unknown = set(header) - set(knownkeys)
			if unknown:
				raise ValueError("unknown header keys: " + ','.join(unknown))
			
			bh = {k : v.encode() for (k, v) in header.items()}
			if 'description' not in bh:
				bh['description'] = b''
				
			dlen = min(len(bh['description']), 36)
			self.header = struct.pack('20s2s2s{}s'.format(dlen),
				*(bh[k] for f in knownkeys)
			)
		
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
			if self.header:
				print("S0" + self._make_srec(b'0000' + bytearray(self.header)), file=f)
				
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
					

class HexOutput(_SrecordDataOutput):
	"""
	Represents a file to written out as Intel HEX data.
	
	Only the 32-bit linear addressing mode is currently supported for output.
	Because segment addresses went out of fashion in the 1980's, and I simply
	refuse to implement them here.  Someone else is welcome to.
	
	Args:
		sdata: The data to be written to the HEX file.
		
		filename: Shortcut to immediately call write() against this file.

		start_address: If provided, adds an execution start address record
			into the HEX file.
			
		bytes_per_line: Maximum number of data bytes per line.
	
	"""
	
	def __init__(self, sdata:SparseData, filename:str=None,
					start_address:int=None,
					bytes_per_line:int=32
					):
						
		self.start_address = start_address
		self.bytes_per_line = bytes_per_line
						
		super().__init__(sdata, filename)
	
	def _make_record(self, address:int, type:int, data:bytes):
		"""Return a HEX record."""
		record = bytes([len(data), address >> 8, address & 0xFF, type]) + data
		checksum = -sum(record) & 0xFF
		return ':{}{:02X}'.format(record.hex().upper(), checksum)
	
	def _chunky(self, dc:DataChunk):
		"""Iterate over chunks of a DataChunk.
		
		Yields: (highaddr, lowaddr, data) where highaddr is the upper 16-bits
			of the address, lowaddr is the lower 16-bits of the address of the
			start of data, and data are the data bytes.  No yielded element will 
			cross a highaddr boundary.
		"""
		
		offset = end = dc.start()
		while end < dc.end():
			start = end
			end = min(dc.end(), start+self.bytes_per_line)
			
			sh = start >> 16
			eh = end >> 16
			if eh != sh:
				end = (start | 0xFFFF) + 1
			
			yield (sh, start & 0xFFFF, dc[start-offset:end-offset])
	
	def write(self, filename):
		if self.sdata.end() >= (2**32):
			raise ValueError(
				"can't express data in 32-bit addresses".format(self.address_bytes)
			)

		# And actually write out the file
		with open(filename, 'w') as f:
			high = None
			for chunk in self.sdata:
				for h, addr, data in self._chunky(chunk):
					if h != high:
						# Need to issue a new high address
						high = h
						d = bytes([h >> 8, h & 0xFF])
						print(self._make_record(0, 4, d), file=f)
					
					# Write out the data record
					print(self._make_record(addr, 0, data), file=f)
	
			# Next, any execution start stuff.
			sa = self.start_address
			if sa is not None:
				d = bytes([(sa >> x) & 0xFF for x in (24, 16, 8, 0)])
				print(self._make_record(0, 5, d), file=f)
 
			# Finally put an EOF record.
			print(self._make_record(0, 1, b''), file=f)

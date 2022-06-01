"""
SparseData transform functions.

These functions manipulate SparseData.  In general, they will modify
the original data, although this shouldn't be assumed.  Instead, the
correct way to call them will always be:

	>>> data = tranformfunction(data)
	
The one exception to this is the duplicate function, which makes a
complete deep copy of the original data.  This is the only safe way
to work with two different copies of the SparseData.

	>>> data_copy = duplicate(data)

"""

from .core import *

import copy
import itertools

def duplicate(sdata):
	"""Make a deep copy of sdata."""
	return copy.deepcopy(sdata)
	
def crop(sdata, start, end):
	"""Slice out only the portion of sdata that lies between start and end."""
	
	def address_slice(dc):
		startpos = max(start - dc.base, 0)
		endpos = min(end - dc.base, len(dc))
		
		if (endpos < 0) or (startpos >= len(dc)):
			return DataChunk(dc.base, bytearray())
		else:
			return dc[startpos:endpos]
	
	return SparseData(address_slice(x) for x in sdata)
	
def offset(sdata, offset):
	"""
	Move sdata in memory.  A positive offset will add to all of the addresses,
	a negative offset will subtract from them.  Addresses can be increased
	without limit, but when decreasing them, an OverflowError will be thrown
	if there is an attempt to create, even temporarily, a negative address.
	
	"""  
	for chunk in sdata:
		new_base = chunk.base + offset
		if (new_base < 0):
			raise OverflowError("Negative start address: {0} + {1} = {2}", chunk.base, offset, new_base)
		chunk.base = new_base
	return sdata

def _bit_reverse(x):
	"""Reverse the bits in a byte."""
	x = ((x & 0xAA) >> 1) | ((x & 0x55) << 1)
	x = ((x & 0xCC) >> 2) | ((x & 0x33) << 2)
	x = ((x & 0xF0) >> 4) | ((x & 0x0F) << 4)
	return x
	
_bit_reverse_table = tuple(_bit_reverse(x) for x in range(256))

def bitswap(sdata):
	"""Reverse the bits in every byte."""
	for chunk in sdata:
		for i in range(len(chunk)):
			chunk[i] = _bit_reverse_table[chunk[i]]
	return sdata

def swap16(sdata):
	"""Flip every two bytes; a 16-bit endian translation."""
	for chunk in sdata:
		for st in range(0,len(chunk),2):
			chunk[st:st+2] = reversed(chunk[st:st+2])
	return sdata
		
def swap32(sdata):
	"""Flip every four bytes; a 32-bit endian translation."""
	for chunk in sdata:
		for st in range(0,len(chunk),4):
			chunk[st:st+4] = reversed(chunk[st:st+4])
	return sdata
	
def rll0(sdata):
	"""
	Perform RLL0 compression on each block in the data.
	
	Each block will continue to start at the same place it had, but
	the end will hopefully move backwards.
		
	RLL0 turns a run of n consecutive zero bytes into the two byte 
	sequence 0, n. (1 <= n <= 256), where n=0 is used for 256. A 
	single zero would therefore be the two byte string 0, 1, and a 
	run of 20 zeros would be 0, 20.

	"""
	def compress(chunk):
		outarray = DataChunk(chunk.start(), [])
		i = 0
		zeros = 0
		for c in chunk:
			if (c == 0):
				zeros += 1
				if (zeros == 256):
					outarray.extend([0, 0])
					zeros = 0
					
			else:
				if (zeros != 0):
					outarray.extend([0, zeros])
					zeros = 0
				outarray.append(c)
			
		if (zeros != 0):
			outarray.extend([0, zeros])
		
		return outarray
		
	return SparseData(compress(c) for c in sdata)

"""
Represents data generator classes.  These classes generate SparseData
structures, the same as if they had been read from files.  These can
then be added into other SparseData.

Constant Generators
====================

Constant generators all follow the prototype::

	sdata = constantgen(address, data, **kwargs)
	
where address is the base address for the new data and data is either
a single constant or an iterable.

Constant generators respect the following parameters, which
will be read from the global srecord settings if they are not
be passed in as keyword arguments:
	
	endian (default LE)
		settings.LE or settings.BE for little and big-endian
		respectively.  This affects the translation of multi-byte 
		integer data into bytes.
		
"""

import struct
import itertools
import copy

from .core import *
from . import settings
settings.set(endian = settings.LE)

def constant8(address, data, **kwargs):
	"""
	8-bit integer constant.
	
	data is either a single integer or a finite iterable of integers.
	Returns as many bytes as there were integers.
	
	"""
	try:
		# Assume it's not iterable first
		bindata = bytearray([data])
		
	except TypeError:
		# Okay, maybe it is.
		bindata = bytearray(data)
	
	return SparseData(DataChunk(address, bindata))
	
def constant16(address, data, **kwargs):
	"""
	16-bit integer constant.
	
	data is either a single integer or a finite iterable of integers.
	Returns 2x as many bytes as there were integers.
	
	"""
	endian = settings.get('endian', kwargs)
	packer = struct.Struct(settings.pack_string(endian, 2))
	try:
		bindata = ''.join(packer.pack(x) for x in data)
		
	except TypeError:
		# Not iterable.  Okay, sure.
		bindata = packer.pack(data)
	
	return SparseData(DataChunk(address, bindata))
	
def constant32(address, data, **kwargs):
	"""
	32-bit integer constant.
	
	data is either a single integer or a finite iterable of integers.
	Returns 4x as many bytes as there were integers.
	
	"""
	endian = settings.get('endian', kwargs)
	packer = struct.Struct(settings.pack_string(endian, 4))
	try:
		bindata = ''.join(packer.pack(x) for x in data)
		
	except TypeError:
		# Not iterable.  Okay, sure.
		bindata = packer.pack(data)
	
	return SparseData(DataChunk(address, bindata))

def constantString(address, data, **kwargs):
	"""
	String constant.
	
	Returns 1 byte per string character.
	
	"""
	return SparseData(DataChunk(address, data))

def fill(sdata, start, end, source, **kwargs):
	"""
	Create a copy of sdata, with all gaps between start and end filled from source.
	
	Source can be:
		a string, in which case it will be repeated endlessly to fill
		the gaps, starting over again in each new gap.
		
		an integer, in which case, based on its value, one of the integer
		constant generators will be used.
		
		an infinite iterator yielding bytes, in which case the gaps
		will be filled from those bytes.
		
	"""
	
	sdata = copy.deepcopy(sdata)
	
	if isinstance(source, str):
		def block(addr, length):
			seq = itertools.cycle(source)
			return constantString(addr, itertools.islice(seq, length), **kwargs)
			
	elif isinstance(source, int):
		if source <= 0xFF:
			def block(addr, length):
				seq = itertools.repeat(source, length)
				return constant8(addr, seq, **kwargs)
				
		elif source <= 0xFFFF:
			def block(addr, length):
				seq = itertools.repeat(source, length//2)
				return constant16(addr, seq, **kwargs)
		else:
			def block(addr, length):
				seq = itertools.repeat(source, length//4)
				return constant32(addr, seq, **kwargs)
	
	else:
		def block(addr, length):
			seq = itertools.islice(source, length)
			return constant8(addr, seq, **kwargs)
		
	# Walk sdata, finding gaps and filling them.
	while start < end:
		for idx in range(len(sdata)):
			if sdata[idx].start() >= start:
				blockend = min(sdata[idx].start(), end)
				nextstart = sdata[idx].end()
				break
		else:
			# There are no data elements higher than start
			blockend = nextstart = end
			end = 0
			
		fill_data = block(start, blockend-start)
		start = nextstart
		sdata.add(fill_data)
		
	return sdata
	
	

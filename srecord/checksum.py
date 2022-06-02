"""
SparseData checksum functions.

These functions scan through SparseData, treating some number of
bytes as words, and performs various and sundry math on them, 
returning the result as an integer.  The SparseData is
unchanged by checksumming.

All checksum functions follow the prototype::

	result = checksumfunction(sdata, **kwargs)

All checksum functions respect the following parameters, which
will be read from the global srecord settings if they are not
be passed in as keyword arguments::

	endian (default LE)
		settings.LE or settings.BE for little and big-endian
		respectively.  This affects the translation of the raw
		data to words for checksumming.  As the checksum results
		are returned as integers rather than bytearrays, the
		concept of endianness doesn't apply to the resulting data.
			
	force_contiguous_checksum (default True)
		If this is True, an attempt to checksum SparseData containing
		gaps between multiple data regions will throw a NonContiguousError
		This is useful if the corresponding checksum algorithm will be
		taking the data in the gap into account, as is usually the case.
		
	force_integer_wordcount (default True)
		If this is True, an attempt to checksum a region that cannot
		be fit into an integer number of words will throw a 
		NonIntegerWordCountError.
		
		For example, sum32 checksums data as 4-byte halfwords.  This
		settings will cause SparseData containing any DataChunk that is
		not a multiple of 4 bytes long to throw and exception.
		
See the settings module for more information about the global settings.

"""

from functools import wraps
import itertools
import struct

from .core import *

# Configure the default settings for this module.
from . import settings
settings.set(
	endian = settings.LE,
	force_contiguous_checksum = True,
	force_integer_wordcount = True
)

def length(sdata, **kwargs):
	"""
	Returns the length of a SparseData, i.e. the difference
	between the start and the end.
	"""
	return sdata.end() - sdata.start()
	
class NonIntegerWordCountError(Exception):
	pass

# Checksum decorator.
def _checksum(wordsize):
	"""
	Wraps a function in a checkum decorator.
	
	The function to be wrapped should accept an iterable of integers
	and arbitrary keyword arguments, and return a checksum value.  The
	iterable is consumed by reading values; you can't backtrack.
	
	The resulting decorated function will take a SparseData and arbitrary
	keyword arguments.  Some of the keywords will be claimed by the engine,
	but all will be passed along to the underlying function.  The underlying
	function will be fed integers of wordsize bytes.
	
	Keyword arguments recognized by the checksum engine are:
		endian
			Sets the read endianness, either BE or LE
			
		force_contiguous_checksum
			If True, throw an exception when asked to checksum sdata
			with multiple regions
			
		force_integer_wordcount
			If True, throw an exception when asked to checksum a region
			that does not divide evenly by the number of bytes per word.
			
	If any of these arguments are not provided, the module-wide defaults
	will be used.  I can't imagine a case in which you'd ever want to
	override the defaults for one call, but hey, it's there.
	
	Example: Sum the entire SparseData one halfword at a time, then
	one word at a time.
	
	@checksum(2)
	def sum16(data, **kwargs):
		return sum(data) & 0xFFFF
	
	@checksum(4)
	def sum32(data, **kwargs):
		return sum(data) & 0xFFFFFFFF
	
	"""
	def decorator(fn):
		@wraps(fn)
		def checksum_wrapper(sdata, **kwargs):
			# Check the validity of the sdata
			if len(sdata) == 0:
				return None
			if len(sdata) > 1 and settings.get('force_contiguous_checksum', kwargs):
				raise NonContiguousError("Not allowed to checksum multiple regions.")
				
			# Set up the correct parser.
			root = settings.pack_string(settings.get('endian', kwargs), wordsize, '{0}')
			
			def chunk_maker(sd, r, iwc):
				for chunk in sd:
					(q, r) = divmod(len(chunk), wordsize)
					if (r != 0) and iwc:
						raise NonIntegerWordCountError("Can't divide into {0} byte pieces.".format(wordsize), chunk)
						
					for data in struct.unpack(root.format(q), bytes(chunk[0:(len(chunk)-r)])):
						yield data
				
			return fn(chunk_maker(sdata, root, settings.get('force_integer_wordcount', kwargs)))
			
		return checksum_wrapper
	return decorator
	
@_checksum(1)
def sum8(data, **kwargs):
	"""8-bit sum of all the bytes."""
	return sum(data) & 0xFF
	
@_checksum(2)
def sum16(data, **kwargs):
	"""16-bit sum of all the 16-bit words."""
	return sum(data) & 0xFFFF 
	
@_checksum(4)
def sum32(data, **kwargs):
	"""32-bit sum of all the 32-bit words."""
	return sum(data) & 0xFFFFFFFF 
	
@_checksum(2)
def fletcher32(data, **kwargs):
	"""
	32-bit Fletcher's checksum.
	
	Lower 16-bits are the modulo-65535 sum of all 16-bit words.
	Upper 16-bits are the modulo-65535 sum of the running sum.
	
	The addition of the upper half adds order-dependance to the
	checksum.  See http://en.wikipedia.org/wiki/Fletcher's_checksum
		
	"""
	
	sum1 = 0xFFFF
	sum2 = 0xFFFF
	
	for ic in iterate_count(data, 360):
		for d in ic:
			sum1 += d
			sum2 += sum1
			
		sum1 = (sum1 & 0xFFFF) + (sum1 >> 16);
		sum2 = (sum2 & 0xFFFF) + (sum2 >> 16);
		
	sum1 = (sum1 & 0xFFFF) + (sum1 >> 16);
	sum2 = (sum2 & 0xFFFF) + (sum2 >> 16);
	return (sum2 << 16) + sum1
	
	

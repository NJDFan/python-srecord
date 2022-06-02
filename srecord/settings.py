"""
Stores global settings for the srecord package.  Endianness, a few
constants, etc.  These should be accessed using the get/set
functions, not directly against the _settings struct.

Relevant functions in the transform, checksum, and generator modules
can check for the default settings in this module, and will use them
if no keyword arguments overriding them are provided.  The best example
of this is endianness.  All functions dealing with multibyte integers
support endianness control, and generally the entire project will
have the same endianness.  Therefore, the simple thing to do is
just to set the global endianness, one of:

	>>> settings.set(endian = settings.LE)
	>>> settings.set(endian = settings.BE)

Having set the endian setting, multibyte functions will use it as so:

	>>> settings.set(endian = settings.BE)
	>>> data = constant16(0, xrange(8))
	>>> data
	SparseData(DataChunk(0x0,b'\x00\x00\x00\x01\x00\x02\x00\x03\x00\x04\x00\x05\x00\x06\x00\x07'))
	>>> checksum.sum16(data)
	28
	>>> checksum.sum16(data, endian = settings.LE)
	7168
	
Notice that in the second call to sum16, the endianness was explicitly
provided as little-endian, which overrides the global setting for the
purpose of that one function call.

Other modules will use other global settings; which ones they are will
be documented with them.

"""

########################################################################
# Constants

BE = 1
LE = 2

_wordsize_char = {
	1 : 'B',	# Byte
	2 : 'H',	# Halfword
	4 : 'L',	# Longword
	8 : 'Q'		# Quadword
}

_endian_char = {
	BE : '>',
	LE : '<'
}

########################################################################
# Parameters

_settings = {
	'endian' : LE,
	'collision_error' : True,
	'force_contiguous_checksum' : True,
	'force_integer_wordcount' : True
}

########################################################################
# Fancy functions

def get(key, overrides=None):
	"""
	Get a setting value, from the overrides if present or the
	global defaults if necessary.
	
	"""
	global _settings
	try:
		return overrides[key]
		
	except (TypeError, KeyError):
		# It's not in the overrides list, return the local
		# module setting for it.
		return _settings[key]
		
def set(**kwargs):
	"""Set global default values."""
	global _settings
	_settings.update(**kwargs)

def pack_string(endian, wordsize, nwords=''):
	"""
	Returns a struct pack/unpack formatting string.
	
	Examples
	
	# Pack string for a single big-endian 2-byte word:
	>>> settings.pack_string(settings.BE, 2)
	'>H'
	# Pack string for 16 litte-endian 4-byte words:
	>>> settings.pack_string(settings.LE, 4, 16)
	'<16L'
	
	"""
	return _endian_char[endian] + str(nwords) + _wordsize_char[wordsize]

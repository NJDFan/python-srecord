"""
Provides data representation for addressed binary data.

Fundamentally, there are two classes here.  DataChunk represents
one block of binary data with a given start address.  SparseData
is a collection of DataChunks.

SparseData elements can be combined by using the .add operator of
one to fold in the other.  They can be duplicated using the
duplicate transform, in the transform module.

"""

import copy
import itertools

from . import settings

from warnings import warn
from typing import List, Sequence

# Various exceptions.
class CollisionError(Exception): pass
class NonContiguousError(Exception): pass

class DataChunk(bytearray):
	"""
	Holds one contiguous block of binary data.
	Provides start and end address information.
	
	>>> x = DataChunk(0x1000, range(8))
	>>> x.start()
	4096
	>>> x.end()
	4104
	
	Slicing a DataChunk with a standard slice returns
	a new DataChunk object.  Slicing with an extended
	slice (nonzero step) returns a bytearray.
	
	Bare DataChunks should never be used; pass them
	around wrapped in SparseData elements instead.
	"""
	
	def __init__(self, base_address, data = None):
		if data:
			super(DataChunk, self).__init__(data)
		else:
			super(DataChunk, self).__init__()
		
		self.base = base_address
		
	def __deepcopy__(self, memo):
		return DataChunk(self.base, self[:])
		
	def __repr__(self):
		if len(self) > 16:
			contents = "b'{0}...' ({1} bytes))".format(''.join(r'\x{0:02X}'.format(s) for s in self[0:4]), len(self))
		else:
			contents = "b'{0}'".format(''.join(r'\x{0:02X}'.format(s) for s in self))
			
		return "DataChunk(0x{0:X},{1})".format(self.base, contents)
		
	def start(self):
		return self.base
	
	def end(self):
		return self.base + len(self)
		
	def __getitem__(self, item):
		
		retval = super(DataChunk, self).__getitem__(item)
		
		if isinstance(item, slice):
			# If this is a non-extended slice, then we can return
			# a new DataChunk.
			start, stop, step = item.indices(len(self))
			if (step == 1):				
				base_address = self.base + start
				return DataChunk(base_address, retval)
				
		else:
			# Anything else is no longer representative of a contiguous
			# space, so just return what the bytearray would.
			return retval
		
class SparseData:
	"""
	Holds sparse binary data as a sorted list of DataChunks.
	
	Args:
		*args: Data chunks to be collected together.
		collision_error (bool): Override the global collision_error setting
			when creating this object.
	
	Attributes:
		collision_error (bool): If True, generate a CollisionError
			when adding a chunk of data that overlaps existing data.
	"""
	
	def __init__(self, *args:DataChunk, **kwargs):
		self.collision_error = settings.get('collision_error', kwargs)
		self._data = list()
		self.add(*args)
		
	def _addone(self, chunk):
		# Find the correct place for this chunk in the sorted
		# _data list.  We'll never have so many chunks that anything
		# smarter than a linear search pays.
		#
		
		# We're going to demand that things inherit from DataChunk.
		# It's just easier than trying to be general in here.
		if not isinstance(chunk, DataChunk):
			raise TypeError("SparseData can only hold DataChunk objects.")
		
		# If the chunk is empty, just skip it
		if len(chunk) == 0:
			return
		
		lbound = 0
		ubound = len(self._data)
		
		for (idx, d) in enumerate(self._data):
			if d.end() < chunk.start():
				# This chunk will go below us.
				lbound = idx + 1
				
			elif d.end() == chunk.start():
				# Merge with this lower chunk
				lbound = idx
				chunk = DataChunk(d.start(), d + chunk)
				
			elif d.start() > chunk.end():
				# This chunk will go above us.
				ubound = idx
				break
				
			elif d.start() == chunk.end():
				# Merge with this higher chunk
				chunk = DataChunk(chunk.start(), chunk + d)
				ubound = idx + 1
				break
				
			else:
				# d is neither entirely higher nor entirely
				# lower than chunk.  That means it must
				# overlap.
				if self.collision_error:
					raise CollisionError("Collision against {0!r} while adding {1!r}".format(d, chunk))
					
				# If we're not going to raise an exception, then
				# assume that the new overwrites the old.
				
				if chunk.start() > d.start():
					chunk[0:0] = d[0:chunk.start()-d.start()]
					chunk.base = d.base
					lbound = idx
				
				if d.end() > chunk.end():
					chunk.extend(d[chunk.end()-d.end():])
					ubound = idx
					
		self._data[lbound:ubound] = [ chunk ]
			
	def set_collision_error(self, boolean):
		warn("Use obj.collision_error = x rather than obj.set_collision_error(x)", DeprecationWarning, stacklevel=2)
		self.collision_error = bool(boolean)
		
	def get_collision_error(self):
		warn("Use obj.collision_error rather than obj.get_collision_error()", DeprecationWarning, stacklevel=2)
		return self.collision_error
			
	def add(self, *args:DataChunk):
		"""
		Add one or more DataChunks into the list.  Adjacent chunks
		will be merged.  Overlapping chunks will allow the latest
		one written to win, unless collision_error = True, in
		which case a CollisionException will be thrown.
		"""
		for a in args:
			try:
				# Start by assuming that a is a DataChunk
				self._addone(a)
				
			except TypeError:
				# Maybe it was an iterable of DataChunks instead?
				for aa in a:
					self._addone(aa)
	
	def __repr__(self):
		return "SparseData({0})".format(",".join(repr(d) for d in self._data))
	
	def __len__(self):
		return len(self._data)

	def __getitem__(self, key):
		return self._data[key]

	def __delitem__(self, key):
		"""DataChunks can be deleted, but not simply replaced."""
		del self._data[key]
		
	def start(self) -> int:
		"""The first address of the first chunk of data."""
		try:
			return self._data[0].start()
		except IndexError:
			return None
			
	def end(self) -> int:
		"""The last address of the last chunk of data."""
		try:
			return self._data[-1].end()
		except IndexError:
			return None

def iterate_count(iterable, n):
	# From a sequence of arbitrary length, yields a list of up to
	# n elements.
	
	while True:
		L = list(itertools.islice(iter(iterable), n))
		if L:
			yield L
		else:
			break
	

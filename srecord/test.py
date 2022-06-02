"""
Unit tests for the srecord stuff.
"""

import unittest
import random
import itertools
import os
import re
import pdb
import struct

from . import *
from .core import *

def getAddressRange(sdata, start, length):
	for chunk in sdata:
		if chunk.end() >= start:
			# This is the only chunk that might work.
			if (chunk.start() > start) or (chunk.end() < (start + length)):
				raise NonContiguousError("Requested address range is not found in one chunk.")
			
			base_address = start - chunk.start()
			return bytearray(chunk[base_address:(base_address + length)])
	
	raise NonContiguousError("Unable to find requested address range.")
	
class CoreTest(unittest.TestCase):
	"""Test the core data structures, DataChunk and SparseData."""
	
	def setUp(self):
		# Set up the global
		settings.set(collision_error = True)
		
		# Provide a couple simple DataChunks
		self.dc1 = DataChunk(0x0, range(255))
		self.dc2 = DataChunk(0x1000, range(255,-1,-1))
		
		self.lorem = "Lorem ipsum dolor sit amet, consectetur adipiscing elit.".encode('utf-8')
		self.dc3 = DataChunk(0x2000, self.lorem)

		self.sdata = SparseData(self.dc1, self.dc3)
		self.sdata.add(self.dc2)
		
	def test_DataChunkParams(self):
		self.assertEqual(self.dc1.start(), 0)
		self.assertEqual(self.dc2.end(), 0x1100)
		self.assertEqual(len(self.dc3), len(self.lorem))
		
	def test_DataChunkSlice(self):
		dc = self.dc2[10:20]
		self.assertEqual(dc.start(), 0x1000 + 10)
		self.assertEqual(dc.end(), 0x1000 + 20)
		self.assertEqual(dc, bytearray(range(245, 235, -1)))
	
	def test_SparseDataParams(self):
		self.assertEqual(len(self.sdata), 3)
		self.assertEqual(self.sdata.start(), self.dc1.start())
		self.assertEqual(self.sdata.end(), self.dc3.end())
		
	def test_SparseDataSet(self):
		try:
			self.sdata[2] = self.dc1
		except AttributeError:
			got_error = True
		else:
			got_error = False
		self.assertTrue(got_error, "No AttributeEror on self.sdata[2] = self.dc1.")
		
	def test_SparseDataStartDel(self):
		del self.sdata[0]
		self.assertEqual(len(self.sdata), 2)
		self.assertEqual(self.sdata.start(), self.dc2.start())
		self.assertEqual(self.sdata.end(), self.dc3.end())
		
	def test_SparseDataMidDel(self):
		del self.sdata[1]
		self.assertEqual(len(self.sdata), 2)
		self.assertEqual(self.sdata.start(), self.dc1.start())
		self.assertEqual(self.sdata.end(), self.dc3.end())
		
	def test_SparseDataLastDel(self):
		del self.sdata[2]
		self.assertEqual(len(self.sdata), 2)
		self.assertEqual(self.sdata.start(), self.dc1.start())
		self.assertEqual(self.sdata.end(), self.dc2.end())
		
	def test_CollisionRaise(self):
		dc = DataChunk(0xFFE, "And BOOM goes the rocket ship.".encode())
		self.assertRaises(CollisionError, self.sdata.add, dc)
		
	def test_CollisionOkayLocal(self):
		dc = DataChunk(0xFFE, "And BOOM goes the rocket ship.".encode())
		self.sdata.collision_error = False
		self.sdata.add(dc)
		self.assertEqual(self.sdata[1].start(), 0xFFE)
		self.assertEqual(self.sdata[1].end(), 0x1100)
		
	def test_CollisionGlobal(self):
		settings.set(collision_error = False)
		sdata = SparseData()
		self.assertFalse(sdata.collision_error)

class FileformatTest(unittest.TestCase):
	"""Test the input and output file classes against each other."""
	
	def setUp(self):
		self.sdata = generator.constant16(0x0000,  (x & 0xFFFF for x in range(1024)), endian=settings.BE)
		self.sdata.add(generator.constant8(0x1000, (random.randint(0, 255) for x in range(1024))))
		self.sdata.add(generator.constant8(0x2000, (random.randint(0, 255) for x in range(1024))))
		self.sdata.add(generator.constant8(0x3000, (random.randint(0, 255) for x in range(1024))))

	def checkSparseData(self, InputRecord):
		sdata = InputRecord.data
		
		self.assertEqual(len(self.sdata), len(sdata))	
		for (n, chunk) in enumerate(self.sdata):
			chunk2 = sdata[n]
			self.assertEqual(chunk.start(), chunk2.start())
			self.assertEqual(bytearray(chunk), bytearray(chunk2))
	
	def checkSecondLine(self, filename, match):
		with open(filename, 'r') as f:
			line = f.readline()
			self.assertTrue(re.match("S0[0-9A-F]+\s*", line, re.I))
			line = f.readline()
			self.assertEqual(match, line.strip())
	
	def test_S19(self):
		sro = output.SrecOutput(self.sdata, 'test.s19', header='Test with 2 address bytes.')
		self.assertEqual(sro.address_bytes, 2)
		self.checkSecondLine('test.s19', 'S12300000000000100020003000400050006000700080009000A000B000C000D000E000F64')
		self.checkSparseData(input.SrecInput('test.s19'))
		os.remove('test.s19')
		
	def test_S28(self):
		output.SrecOutput(self.sdata, 'test.s28', address_bytes=3, header='Test with 3 address bytes.')
		self.checkSecondLine('test.s28', 'S2240000000000000100020003000400050006000700080009000A000B000C000D000E000F63')
		self.checkSparseData(input.SrecInput('test.s28'))
		os.remove('test.s28')
		
	def test_S37(self):
		output.SrecOutput(self.sdata, 'test.s37', address_bytes=4, header='Test with 4 address bytes.')
		self.checkSecondLine('test.s37', 'S325000000000000000100020003000400050006000700080009000A000B000C000D000E000F62')
		self.checkSparseData(input.SrecInput('test.s37'))
		os.remove('test.s37')
		
	def test_binary(self):
		self.assertRaises(NonContiguousError, output.BinaryOutput, self.sdata, 'test.bin')
		self.sdata = generator.fill(self.sdata, self.sdata.start(), self.sdata.end(), 0xFFFF)
		
		output.BinaryOutput(self.sdata, 'test.bin')
		with open('test.bin', 'rb') as f:
			chunk = f.read(256)
			self.assertEqual(chunk, struct.pack('>128H', *range(128)))
		
		self.checkSparseData(input.BinaryInput('test.bin'))
		os.remove('test.bin')

class GeneratorTest(unittest.TestCase):
	"""Test out the various generators that aren't fill."""

	def setUp(self):
		settings.set(endian = settings.LE)

	def test_constant8(self):
		sdata = generator.constant8(0x2000, range(256))
		self.assertEqual(len(sdata),		1)
		self.assertEqual(sdata[0].start(),	0x2000)
		self.assertEqual(sdata[0].end(),	0x2100)
		self.assertEqual(sdata[0][100],	100)
		
	def test_constant16(self):
		sdata = generator.constant16(0x2000, range(256))
		self.assertEqual(len(sdata),			1)
		self.assertEqual(sdata[0].start(),		0x2000)
		self.assertEqual(sdata[0].end(),		0x2200)
		self.assertEqual(sdata[0][100:102],	bytearray([50, 0]))
		
	def test_constant32(self):
		sdata = generator.constant32(0x2000, range(256), endian=settings.BE)
		self.assertEqual(len(sdata),			1)
		self.assertEqual(sdata[0].start(),		0x2000)
		self.assertEqual(sdata[0].end(),		0x2400)
		self.assertEqual(sdata[0][100:104],	bytearray([0, 0, 0, 25]))
		
	def test_constantBytes(self):
		sdata = generator.constant(0x2000, b"The quick brown fox jumps over the lazy dogs.")
		self.assertEqual(len(sdata),			1)
		self.assertEqual(sdata[0].start(),		0x2000)
		self.assertEqual(sdata[0].end(),		0x2000 + 45)
		
		self.assertEqual(
			bytearray(sdata[0][4:9]),
			b'quick'
		)
		
	def test_constantString(self):
		sdata = generator.constantString(0x2000, "The quick brown fox jumps over the lazy dogs.")
		self.assertEqual(len(sdata),			1)
		self.assertEqual(sdata[0].start(),		0x2000)
		self.assertEqual(sdata[0].end(),		0x2000 + 45)
		
		self.assertEqual(
			bytearray(sdata[0][4:9]).decode(),
			'quick'
		)
		
class FillTest(unittest.TestCase):
	"""Test out the fill generator."""

	def setUp(self):
		settings.set(endian = settings.LE)
		
		a = generator.constant8(0x100, [3, 1, 4, 1, 5, 9, 2, 3])
		a.add(generator.constantString(0x200, 'Now is the time for all good men to come to the aid of their country.'))
		a.add(generator.constantString(0x300, 'The quick brown fox jumped over the lazy dogs.'))
		self.sdata = a

	def checkSpans(self, *spans):
		# Check that the address ranges are expected
		self.assertEqual(len(self.sdata), len(spans))
		for (chunk, span) in zip(self.sdata, spans):
			chunkrange = (chunk.start(), chunk.end())
			self.assertEqual(chunkrange, span)
			
		# And we'll always check that the expected data is still the same
		self.assertEqual(
			getAddressRange(self.sdata, 0x100, 8),
			bytearray([3, 1, 4, 1, 5, 9, 2, 3])
		)
		self.assertEqual(
			getAddressRange(self.sdata, 0x200, 69),
			bytearray(b'Now is the time for all good men to come to the aid of their country.')
		)
		self.assertEqual(
			getAddressRange(self.sdata, 0x300, 46),
			bytearray(b'The quick brown fox jumped over the lazy dogs.')
		)

	def test_fillLowOverlap(self):
		end = self.sdata.end()
		self.sdata = generator.fill(self.sdata, 0x80, 0x280, 0xFF)
		self.checkSpans(
			(0x080, 0x280),
			(0x300, 0x32E)
		)
		
	def test_fillHighOverlap(self):
		self.sdata = generator.fill(self.sdata, 0x180, 0x380, 0xFF)
		self.checkSpans(
			(0x100, 0x108),
			(0x180, 0x380)
		)
		
	def test_fillCompleteOverlap(self):
		self.sdata = generator.fill(self.sdata, 0, 0x400, b"SPOON!")
		self.checkSpans(
			(0, 0x400)
		)
		self.assertEqual(getAddressRange(self.sdata, 0, 12), b'SPOON!SPOON!')
		
	def test_fillNoOverlap(self):
		def ProvideCount():
			x = 0
			while True:
				yield x
				x = (x + 1) & 0xFF
		
		self.sdata = generator.fill(self.sdata, 0x180, 0x1C0, ProvideCount())
		self.checkSpans(
			(0x100, 0x108),
			(0x180, 0x1C0),
			(0x200, 0x245),
			(0x300, 0x32E)
		)
		self.assertEqual(self.sdata[1], bytearray(range(0x40)))
		
	def test_fillLineup(self):
		self.sdata = generator.fill(self.sdata, 0x200, 0x300, b"SPOON!")
		self.checkSpans(
			(0x100, 0x108),
			(0x200, 0x32E)
		)
		
class TestChecksumLE(unittest.TestCase):
	"""Test out the various checksum algorithms."""

	def setUp(self):
		settings.set(endian = settings.LE)
		self.sdata = generator.constant16(0x1000, range(256)) 
		
	def test_sum8(self):
		self.assertEqual(checksum.sum8(self.sdata), sum(range(256)) & 0xFF)
		
	def test_sum16(self):
		self.assertEqual(checksum.sum16(self.sdata), sum(range(256)))
		
	def test_sum32(self):
		# We're little-endian, so the lower valued data will be
		# in the LSW locations.
		target = sum(range(0, 256, 2)) + (sum(range(1, 256, 2)) << 16)
		self.assertEqual(checksum.sum32(self.sdata), target)
		
	def test_fletcher32(self):
		# Each word gets added in over and over again based on its
		# position.
		sum1 = sum(range(256)) % 65535
		sum2 = sum((256 - x) * x for x in range(256)) % 65535
		
		self.assertEqual(checksum.fletcher32(self.sdata), (sum2 << 16) | sum1)

class TestChecksumBE(TestChecksumLE):
	"""Test out the various checksum algorithms, but big-endian."""

	def setUp(self):
		settings.set(endian = settings.BE)
		self.sdata = generator.constant16(0x1000, range(256)) 
		
	def test_sum32(self):
		# We're big-endian, so the lower valued data will be
		# in the MSW locations.
		target = (sum(range(0, 256, 2)) << 16) + sum(range(1, 256, 2))
		self.assertEqual(checksum.sum32(self.sdata), target)
		
	def test_fletcher32(self):
		# Each word gets added in over and over again based on its
		# position.
		sum1 = sum(range(256)) % 65535
		sum2 = sum((256 - x) * x for x in range(256)) % 65535
		
		self.assertEqual(checksum.fletcher32(self.sdata), (sum2 << 16) | sum1)
		
class TestTransforms(unittest.TestCase):
	"""Test out the various transform algorithms."""
	
	def setUp(self):
		settings.set(endian = settings.LE)
		self.sdata = generator.constant8(0x1000, range(256)) 
		self.sdata.add(generator.constant8(0x2000, range(256)))
	
	def assertUnchanged(self, verifydata):
		for chunk in verifydata:
			for (x, data) in enumerate(chunk):
				self.assertEqual(x, data)
		
	def test_bitswap(self):
		self.sdata = transform.bitswap(self.sdata)
		self.assertEqual(self.sdata.start(),	0x1000)
		self.assertEqual(self.sdata.end(),		0x2100)
		
		for chunk in self.sdata:
			for x in range(256):
				data = chunk[x]
				
				data = ((data & 0xF0) >> 4) | ((data & 0x0F) << 4)
				data = ((data & 0xCC) >> 2) | ((data & 0x33) << 2)
				data = ((data & 0xAA) >> 1) | ((data & 0x55) << 1)
				
				self.assertEqual(data, x)
		
	def test_crop(self):
		self.sdata = transform.crop(self.sdata, 0x9F0, 0x1010)
		self.assertEqual(len(self.sdata),		1)
		self.assertEqual(self.sdata.start(),	0x1000)
		self.assertEqual(self.sdata.end(),		0x1010)
		self.assertUnchanged(self.sdata)
		
	def test_duplicate(self):
		newdata = transform.duplicate(self.sdata)
		self.assertFalse(newdata is self.sdata)
		
		newdata.add(generator.constantString(0, 'SPOON!!!'))
		self.assertEqual(len(self.sdata),	2)
		self.assertEqual(len(newdata),		3)
		
		for chunk in newdata:
			for x in range(len(chunk)):
				chunk[x] = 0
				
		self.assertUnchanged(self.sdata)
				
	def test_offset(self):
		self.sdata = transform.offset(self.sdata, 0x1000)
		self.assertEqual(self.sdata[0].start(), 0x2000)
		self.assertEqual(self.sdata[1].start(), 0x3000)
		self.assertUnchanged(self.sdata)
	
	def test_swap16(self):
		self.sdata = transform.swap16(self.sdata)
		self.assertEqual(self.sdata.start(),	0x1000)
		self.assertEqual(self.sdata.end(),		0x2100)
		
		for chunk in self.sdata:
			x = 0
			for data in iterate_count(iter(chunk), 2):
				data.reverse()
				self.assertEqual(data, [x, x+1])
				x += 2
		
	def test_swap32(self):
		self.sdata = transform.swap32(self.sdata)
		self.assertEqual(self.sdata.start(),	0x1000)
		self.assertEqual(self.sdata.end(),		0x2100)
		
		for chunk in self.sdata:
			x = 0
			for data in iterate_count(iter(chunk), 4):
				data.reverse()
				self.assertEqual(data, [x, x+1, x+2, x+3])
				x += 4
				
	def test_rll0(self):
		# import ipdb; ipdb.set_trace()
		sdata = generator.constantString(0x1000, "Hello" + ('\0' * ord('_')) + "World")
		sdata.add(generator.constant8(0x2000, range(1, 101)))
		sdata = transform.rll0(sdata)
		
		self.assertEqual(sdata.start(), 0x1000)
		self.assertEqual(sdata[0], b"Hello\0_World")
		
		self.assertEqual(sdata[1].start(), 0x2000)
		self.assertEqual(sdata[1].end(), 0x2000 + 100)

if __name__ == '__main__':
	unittest.main()

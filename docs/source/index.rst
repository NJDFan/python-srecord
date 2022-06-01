=========================
Srecord Tools for Python
=========================

.. toctree::
   :maxdepth: 4

   api/modules

Functions and structures for working with binary data, with the goal of assembling
a flash or EPROM image for embedded applications.

The basic idea here comes from `SRecord <http://srecord.sourceforge.net/>`_ by 
Peter Miller and Scott Finneran.  Rather than keep with this approach, this 
library provides building blocks that allow a given task to accomplished in a a 
few lines of Python, rather than trying to provide command-line executables 
that are all things to all people.

In my opinion, this simplifies the semantics of explaining exactly what you'd
like to do with the data.  For instance, with *srec_cat*, adding both the
checksum and length of a data block, with neither impacting the other, was
suprisingly difficult.  This is because the command-line processing language
of *srec_cat* has no concept of variables; you can't put a result aside for a
moment and come back to it later.  By integrating it all into Python, and
using Python as our interpreter, all of the flexability of a full-fledged
language becomes available.

Additionally, this radically reduces the number of functions that need to
be written.  Rather than implement a 16-bit checksum, the negative of that
checksum, and the ones' compliment of that checksum all as separate functions
I have simply implemented the sum16 function, and let Python do the rest:

.. code-block:: python

    >>> true_checksum = checksum.sum16(sdata)
    >>> neg_checksum = -checksum.sum16(sdata) & 0xFFFF
    >>> comp_checksum = ~checksum.sum16(sdata) & 0xFFFF

Likewise, generating streams of constants from either random or sequential
numbers are easily implemented on top of a couple basic constant generators:

.. code-block:: python

    # Generate 16 ascending bytes.
    >>> count_data8 = generator.constant8(addr, range(16))
    
    # Generate 16 ascending 32-bit words in big-endian format
    >>> count_data32 = generator.constant32(addr, range(16), endian=settings.BE)
    
    # Generate 256 random bytes.
    >>> import random
    >>> random_data = generator.constant8(addr,
            ((random.randint(0, 255) for x in range(256)))
        )
    
Examples
=========

These libraries are meant to be used in very small programs, and have
been designed to be import * safe.  The recommeded usage is to start
off with 

.. code-block:: python

    >>> from srecord import *
    
This will bring the transform, checksum, input, output, generator, and settings 
modules in, allowing you to call functions and objects from them simply and 
easily.  Note, this does not bring in core.  You shouldn't need core.  You 
shouldn't be making your own SparseData and DataChunk objects from scratch; 
that's what the generator module is for.

With these modules imported, it becomes fairly simple to perform common tasks.  
For instance, our goal is to combine the following objects into one ROM image 
for a 32-bit little-endian processor.

=======     =====   ========
Address     Bytes   Contents
=======     =====   ========
0x0000      4       Preamble (0x12345678)
0x0004      4       Length of Release/firmware.s28 in bytes
0x0008      ???     Release/firmware.s28
        
                    This is our ARM code.  It expects to run at address 0, which is
                    also the address at which it was linked.
0x1000      4       Preamble ('FPGA')
0x1004      4       Length of binaries/FPGA.rbf in bytes
0x1008      ???     binaries/FPGA.rbf
        
                    This is our FPGA image, an Altera .rbf file.  RBF stands for
                    raw binary format, so it knows nothing about addresses.
=======     =====   ========
        
The program to do so is as follows.

.. code-block:: python

    from srecord import *
    
    # Ensure that we're little-endian.  This is the default.
    settings.set(endian = settings.LE)

    # Bring the firmware image in, and move it up.
    firmware_image = input.SrecInput().read('Release/firmware.s28')
    assert firmware_image.start() == 0
    firmware_image = transform.offset(firmware_image, 8)
    
    # Generate the preamble data for the bootloader
    fw_len = checksum.length(firmware_image)
    preamble = generator.constant32(0, [0x12345678, fw_len])
    firmware_image.add(preamble)
    
    # Bring in the FPGA data.  Binaries always start at address 0
    fpga = input.BinaryInput().read('binaries/FPGA.rbf')
    fpga = transform.offset(fpga, 0x1008)
    fpga.add(generator.constant32(0x1004, checksum.length(fpga))
    fpga.add(generator.constantString(0x1000, 'FPGA'))

    # Merge the two and write it out
    firmware_image.add(fpga)
    output.SrecOutput(firmware_image, 'result.s28', address_bytes=3)
    
    # Fill in the gaps with 0xFF and write it as a binary as well.
    firmware_image = generator.fill(
        firmware_image,
        firmware_image.start(),
        firmware_image.end(),
        0xFF
    )
    output.BinaryOutput(firmware_image, 'result.bin')
    
Author
=======
Rob Gaddi
Highland Technology, Inc.

Installation
============

srecord requries Python 3.6 or greater.  Install the srecord package like any 
other Python package.

.. code-block:: console

   $ python3 -m pip install srecord

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

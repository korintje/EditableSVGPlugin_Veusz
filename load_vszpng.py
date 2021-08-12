# -*- coding: utf-8 -*-
from veusz.plugins import ToolsPlugin, toolspluginregistry

class LoadVSZPNGPlugin(ToolsPlugin):
    """Load a re-editable PNG image with internal Veusz code."""
    menu = ('Load Veusz-PNG',)
    name = 'Load Veusz-PNG'
    description_short = 'Load Veusz-PNG image.'
    description_full = 'Load re-editable Veusz-PNG image.'
    
    def __init__(self):
        """Make list of fields."""
        from veusz.plugins import FieldFilename
        self.fields = [
            FieldFilename("filepath", descr="PNG filepath"),
            ]
                    
    def apply(self, interface, fields):
        """
        Load "tEXt" chunk in the PNG file
        when the chunk text starts from "# Veusz" 
        """
        ##########################################################################
        # copied from "png.py" in the module pypng(https://github.com/drj11/pypng)
        # with deletion some unnecessary functions, classes, and modules,
        # in order to provide plugin as a one-file python file.
        # For main function, skip to "pypng module end".
        ##########################################################################
        import collections
        import io
        import itertools
        import math
        import operator
        import re
        import struct
        import warnings
        import zlib
        from array import array

        __all__ = ['Image', 'Reader', 'Writer', 'write_chunks', 'from_array']
        signature = struct.pack('8B', 137, 80, 78, 71, 13, 10, 26, 10)
        Resolution = collections.namedtuple('_Resolution', 'x y unit_is_meter')

        def group(s, n):
            return list(zip(* [iter(s)] * n))

        def isarray(x):
            return isinstance(x, array)

        class Error(Exception):
            def __str__(self):
                return self.__class__.__name__ + ': ' + ' '.join(self.args)

        class FormatError(Error):
            """
            Problem with input file format.
            In other words, PNG file does not conform to
            the specification in some way and is invalid.
            """

        class ProtocolError(Error):
            """
            Problem with the way the programming interface has been used,
            or the data presented to it.
            """

        class ChunkError(FormatError):
            pass

        class Default:
            """The default for the greyscale paramter."""

        def write_chunk(outfile, tag, data=b''):
            """
            Write a PNG chunk to the output file, including length and
            checksum.
            """
            data = bytes(data)
            outfile.write(struct.pack("!I", len(data)))
            outfile.write(tag)
            outfile.write(data)
            checksum = zlib.crc32(tag)
            checksum = zlib.crc32(data, checksum)
            checksum &= 2 ** 32 - 1
            outfile.write(struct.pack("!I", checksum))

        def write_chunks(out, chunks):
            """Create a PNG file by writing out the chunks."""
            out.write(signature)
            for chunk in chunks:
                write_chunk(out, *chunk)

        RegexModeDecode = re.compile("(LA?|RGBA?);?([0-9]*)", flags=re.IGNORECASE)

        class Reader:

            def __init__(self, _guess=None, filename=None, file=None, bytes=None):
                keywords_supplied = (
                    (_guess is not None) +
                    (filename is not None) +
                    (file is not None) +
                    (bytes is not None))
                if keywords_supplied != 1:
                    raise TypeError("Reader() takes exactly 1 argument")
                self.signature = None
                self.transparent = None
                self.atchunk = None
                if _guess is not None:
                    if isarray(_guess):
                        bytes = _guess
                    elif isinstance(_guess, str):
                        filename = _guess
                    elif hasattr(_guess, 'read'):
                        file = _guess
                if bytes is not None:
                    self.file = io.BytesIO(bytes)
                elif filename is not None:
                    self.file = open(filename, "rb")
                elif file is not None:
                    self.file = file
                else:
                    raise ProtocolError("expecting filename, file or bytes array")

            def chunk(self, lenient=False):
                self.validate_signature()
                if not self.atchunk:
                    self.atchunk = self._chunk_len_type()
                if not self.atchunk:
                    raise ChunkError("No more chunks.")
                length, type = self.atchunk
                self.atchunk = None

                data = self.file.read(length)
                if len(data) != length:
                    raise ChunkError(
                        'Chunk %s too short for required %i octets.'
                        % (type, length))
                checksum = self.file.read(4)
                if len(checksum) != 4:
                    raise ChunkError('Chunk %s too short for checksum.' % type)
                verify = zlib.crc32(type)
                verify = zlib.crc32(data, verify)
                verify &= 2**32 - 1
                verify = struct.pack('!I', verify)
                if checksum != verify:
                    (a, ) = struct.unpack('!I', checksum)
                    (b, ) = struct.unpack('!I', verify)
                    message = ("Checksum error in %s chunk: 0x%08X != 0x%08X."
                            % (type.decode('ascii'), a, b))
                    if lenient:
                        warnings.warn(message, RuntimeWarning)
                    else:
                        raise ChunkError(message)
                return type, data

            def chunks(self):
                while True:
                    t, v = self.chunk()
                    yield t, v
                    if t == b'IEND':
                        break

            def validate_signature(self):
                if self.signature:
                    return
                self.signature = self.file.read(8)
                if self.signature != signature:
                    raise FormatError("PNG file has invalid signature.")

            def _chunk_len_type(self):
                x = self.file.read(8)
                if not x:
                    return None
                if len(x) != 8:
                    raise FormatError(
                        'End of file whilst reading chunk length and type.')
                length, type = struct.unpack('!I4s', x)
                if length > 2 ** 31 - 1:
                    raise FormatError('Chunk %s is too large: %d.' % (type, length))
                type_bytes = set(bytearray(type))
                if not(type_bytes <= set(range(65, 91)) | set(range(97, 123))):
                    raise FormatError(
                        'Chunk %r has invalid Chunk Type.'
                        % list(type))
                return length, type

            def process_chunk(self, lenient=False):
                type, data = self.chunk(lenient=lenient)
                method = '_process_' + type.decode('ascii')
                m = getattr(self, method, None)
                if m:
                    m(data)

        def decompress(data_blocks):
            d = zlib.decompressobj()
            for data in data_blocks:
                yield bytearray(d.decompress(data))
            yield bytearray(d.flush())

        ##########################################################################
        # pypng module end
        ##########################################################################

        # Enable all commands under interface
        cmds = [cmd for cmd in dir(interface) if cmd.startswith('__') is False]
        for cmd in cmds:
            exec(f"{cmd} = interface.{cmd}")

        # get the .png filepath
        filepath = fields['filepath']

        # Import normal SVG
        vszscript = ''
        try:
            vszpng = Reader(filename = filepath)
            for chunk in vszpng.chunks():
                tag = chunk[0].decode(errors="ignore")
                content = chunk[1].decode(errors="ignore")
                if tag == "tEXt":
                    if content[:7] == "# Veusz":
                        vszscript = content
        except:
            pass

        if vszscript:
            # Wipe existing widgets
            for child in interface.Root.childnames_widgets:
                interface.Remove(child)
            # Exec saved commands
            exec(vszscript)

toolspluginregistry.append(LoadVSZPNGPlugin)
""" Buffer carving utilties.
"""

from array import array
from ucollections import namedtuple
from uctypes import (
    INT8, UINT8,
    INT16, UINT16,
    BFUINT16,
    BF_POS,
    BF_LEN,
    BIG_ENDIAN,
    addressof,
    struct as uc_struct,
)


def twos_complement(bits, value):
    if value < 0:
        return value + (1 << bits)
    if value >= (1 << (bits - 1)):
        return value - (1 << bits)
    return value

FD_BYTE = object()
FD_WORD = object()

FieldDesc = namedtuple('FieldDesc', ('name', 'layout', 'signed_bits'))
def field_desc(name, bits, pos=0, signed=False):
    if bits is FD_WORD:
        layout = 0 | (INT16 if signed else UINT16)
        return FieldDesc(name, layout, None)
    
    if bits is FD_BYTE:
        layout = pos | (INT8 if signed else UINT8)
        return FieldDesc(name, layout, None)

    layout = 0 | BFUINT16 | pos << BF_POS | bits << BF_LEN
    return FieldDesc(name, layout, bits if signed else None)


class StructProto:
    # data needed to create a Struct
    # can be instantiated once and reused between Struct instances
    def __init__(self, fields):
        self.layout = {}
        self.signed = {}
        for fld in fields:
            self.layout[fld.name] = fld.layout
            if fld.signed_bits is not None:
                self.signed[fld.name] = fld.signed_bits

class Struct:
    def __init__(self, buf, proto):
        self._signed = proto.signed
        self._struct = uc_struct(addressof(buf), proto.layout, BIG_ENDIAN)

    def __getitem__(self, name):
        value = getattr(self._struct, name)
        signed = self._signed.get(name)
        if signed is not None:
            return twos_complement(signed, value)
        return value

    def __setitem__(self, name, value):
        signed = self._signed.get(name)
        if signed is not None:
            value = twos_complement(signed, value)
        setattr(self._struct, name, value)


class ReadOnlyError(Exception): pass


class RegisterMap:
    def __init__(self, iface, register_map, readonly=False):
        # register_map should be a dict of { I2C address : FieldDesc(s) }
        self.iface = iface
        self.readonly = readonly
        self._name_lookup = self._build_lookup(register_map)

    @staticmethod
    def _build_lookup(register_map):
        lookup = {}
        for address, fields in register_map.items():
            if isinstance(fields, FieldDesc):
                fields = (fields,)

            proto = StructProto(fields)
            for fld in fields:
                if fld.name in lookup:
                    raise ValueError(f"duplicate field name: {fld.name}")
                lookup[fld.name] = (address, proto)

        return lookup

    def keys(self):
        return self._name_lookup.keys()

    def __iter__(self):
        return iter(self.keys())
    def __len__(self):
        return len(self._name_lookup)
    def __contains__(self, name):
        return name in self._name_lookup

    def __getitem__(self, name):
        address, proto = self._name_lookup[name]

        buf = self.iface.read(address)
        struct = Struct(buf, proto)
        return struct[name]

    def __setitem__(self, name, value):
        address, proto = self._name_lookup[name]

        if self.readonly:
            raise ReadOnlyError(f"can't write to '{name}': not permitted")

        buf = bytearray(REG_SIZE)
        self.iface.read_into(address, buf)
        struct = Struct(buf, proto)
        struct[name] = value
        self.iface.write(address, buf)


class Array2D:
    def __init__(self, typecode, stride, init):
        self.stride = stride
        self._array = array(typecode, init)
    
    def __getitem__(self, idx):
        i, j = idx
        return self._array[i * self.stride + j]
    def __setitem__(self, idx, value):
        i, j = idx
        self._array[i * self.stride + j] = value

    @classmethod
    def index_range(cls, num_strides, stride):
        # yields i,j pairs for an Array2D with the given shape
        # useful for generating the init sequence
        for i in range(num_strides):
            for j in range(stride):
                yield i, j

    def __len__(self):
        return len(self._array)
    def __iter__(self):
        return iter(self._array)

    def iter_indexed(self):
        num_strides = (len(self._array) + self.stride - 1)//self.stride
        indices = self.index_range(num_strides, self.stride)
        for pair, value in zip(indices, self._array):
            yield pair[0], pair[1], value


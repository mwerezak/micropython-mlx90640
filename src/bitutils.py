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

class Array2D:
    def __init__(self, typecode, stride, init):
        self.stride = stride
        self.array = array(typecode, init)
    
    # preserve array interface for efficient iteration
    def __len__(self):
        return len(self.array)
    def __iter__(self):
        return iter(self.array)
    def __getitem__(self, idx):
        return self.array[idx]
    def __setitem__(self, idx, value):
        self.array[idx] = value

    def get_coord(self, i, j):
        return self.array[i * self.stride + j]
    def set_coord(self, i, j, value):
        self.array[i * self.stride + j] = value

    def iter_indexed(self):
        num_strides = (len(self.array) + self.stride - 1)//self.stride
        indices = self.index_range(num_strides, self.stride)
        for pair, value in zip(indices, self.array):
            yield pair[0], pair[1], value

    # very useful for generating the init sequence
    @classmethod
    def index_range(cls, num_strides, stride):
        # yields i,j pairs for an Array2D with the given shape
        for i in range(num_strides):
            for j in range(stride):
                yield i, j
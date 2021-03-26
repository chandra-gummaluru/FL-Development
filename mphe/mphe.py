from ctypes import *
import numpy as np

so = cdll.LoadLibrary('./_mphe.so')

class Luint64(Structure):
    _fields_ = [
        ('data', POINTER(c_longlong)),
        ('size', c_size_t)
    ]

class Params(Structure):
    _fields_ = [
        ('qi', Luint64),
        ('pi', Luint64),

        ('logN', c_int),
        ('logSlots', c_int),
        
        ('scale', c_double),
        ('sigma', c_double)
    ]

newParams = so.newParams
newParams.restype = POINTER(Params)

if __name__ == '__main__':
    # so.mpheTest()

    ### TEST: Params ###
    params = so.newParams()

    # Convert to numpy array: https://stackoverflow.com/questions/4355524/getting-data-from-ctypes-array-into-numpy
    qi = np.ctypeslib.as_array(params.contents.qi.data, shape=(params.contents.qi.size,))
    print('qi:', qi)

    pi = np.ctypeslib.as_array(params.contents.pi.data, shape=(params.contents.pi.size,))
    print('pi:', pi)

    # Print contents
    print('Params:', params.contents.logN, params.contents.logSlots, params.contents.scale, params.contents.sigma)

    # Update a member
    params.contents.logN = 0
    print('Updated Params:', params.contents.logN, params.contents.logSlots, params.contents.scale, params.contents.sigma)


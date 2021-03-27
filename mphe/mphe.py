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

class Poly(Structure):
    _fields_ = [
        ('coeffs', POINTER(Luint64)),
        ('size', c_size_t)
    ]

newPoly = so.newPoly
newPoly.restype = POINTER(Poly)

class PolyPair(Structure):
    _fields_ = [
        ('p0', POINTER(Poly)),
        ('p1', POINTER(Poly))
    ]

class Ciphertext(Structure):
    _fields_ = [
        ('value', POINTER(Poly)),
        ('size', c_size_t),
        ('scale', c_double),
        ('isNTT', c_bool)
    ]

newCiphertext = so.newCiphertext
newCiphertext.restype = POINTER(Ciphertext)

class Data(Structure):
    _fields_ = [
        ('data', POINTER(Ciphertext)),
        ('size', c_size_t)
    ]

class Share(Structure):
    _fields_ = [
        ('data', POINTER(Poly)),
        ('size', c_size_t)
    ]

class MPHEServer(Structure):
    _fields_ = [
        ('params', Params),
        ('crs', Poly),
        ('secret_key', Poly),
        
        ('data', POINTER(Data)),
    ]

newMPHEServer = so.newMPHEServer
newMPHEServer.restype = POINTER(MPHEServer)

genCRS = so.genCRS
genCRS.restype = POINTER(Poly)

if __name__ == '__main__':
    # # so.mpheTest()

    # ### TEST: Params ###
    # params = so.newParams()
    # print('Params members:', dir(params.contents))

    # # # Convert to numpy array: https://stackoverflow.com/questions/4355524/getting-data-from-ctypes-array-into-numpy
    # qi = np.ctypeslib.as_array(params.contents.qi.data, shape=(params.contents.qi.size,))
    # # print('qi:', qi, 'size:', params.contents.qi.size)

    # pi = np.ctypeslib.as_array(params.contents.pi.data, shape=(params.contents.pi.size,))
    # # print('pi:', pi)

    # # # Print contents
    # # print('PYTHON Params:', params.contents.logN, params.contents.logSlots, params.contents.scale, params.contents.sigma)

    # # # Update a member
    # # params.contents.logN = 0
    # # print('Updated Params:', params.contents.logN, params.contents.logSlots, params.contents.scale, params.contents.sigma)

    # ### TEST: Creating Params from basic Python types ###
    # p = Params()
    # data1 = qi.tolist()
    # data2 = pi.tolist()

    # p.qi = Luint64()
    # p.qi.data = (c_longlong * len(data1))(*data1)
    # p.qi.size = len(data1)

    # p.pi = Luint64()
    # p.pi.data = (c_longlong * len(data2))(*data2)
    # p.pi.size = len(data2)

    # p.logN = params.contents.logN
    # p.logSlots = params.contents.logSlots
    # p.scale = params.contents.scale
    # p.sigma = params.contents.sigma

    # so.printParams(pointer(p))

    # ### TEST: Poly ###
    # pp = newPoly()
    # # print('Poly members:', dir(pp.contents))
    # print('Poly:', pp.contents.coeffs, pp.contents.size)
    # coeffs = []
    # for i in range(pp.contents.size):
    #     npCoeff = np.ctypeslib.as_array(pp.contents.coeffs[i].data, shape=(pp.contents.coeffs[i].size,))
    #     coeffs.append(npCoeff.tolist())
    
    # print('Poly coeffs casted to a list:', len(coeffs), len(coeffs[0]))
    # so.printPoly(pp)

    ### TEST: Ciphertext ###
    # ct = newCiphertext()
    # print('Ciphertext:', ct.contents.value, ct.contents.size, ct.contents.scale, ct.contents.isNTT)
    # so.printCiphertext(ct)

    ### TEST: MPHEServer ###
    server = newMPHEServer()
    print('Server:', server.contents.params, server.contents.crs)
    # CRS = server.contents.crs
    CRS = genCRS(server).contents
    crs = []
    for i in range(server.contents.crs.size):
        npCoeff = np.ctypeslib.as_array(CRS.coeffs[i].data, shape=(CRS.coeffs[i].size,))
        crs.append(npCoeff.tolist())
    print('Poly coeffs casted to a list:', len(crs), len(crs[0]))
    so.printPoly(pointer(server.contents.crs))

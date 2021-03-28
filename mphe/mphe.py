from ctypes import *
import numpy as np

so = cdll.LoadLibrary('./_mphe.so')

class Luint64(Structure):
    _fields_ = [
        ('data', POINTER(c_ulonglong)),
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
        ('p0', Poly),
        ('p1', Poly)
    ]

genPublicKey = so.genPublicKey
genPublicKey.argtypes = [ POINTER(Params), POINTER(Poly) ]
genPublicKey.restype = POINTER(PolyPair)

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
        ('secretKey', Poly),
        
        ('data', Data),
    ]

newMPHEServer = so.newMPHEServer
newMPHEServer.restype = POINTER(MPHEServer)

genCRS = so.genCRS
genCRS.argtypes = [ POINTER(MPHEServer) ]
genCRS.restype = POINTER(Poly)

colKeySwitch = so.colKeySwitch
colKeySwitch.argtypes = [ POINTER(MPHEServer), POINTER(Share), c_size_t ]

colKeyGen = so.colKeyGen
colKeyGen.argtypes = [ POINTER(MPHEServer), POINTER(Share), c_size_t ]
colKeyGen.restype = POINTER(PolyPair)

aggregate = so.aggregate
aggregate.argtypes = [ POINTER(MPHEServer), POINTER(Data), c_size_t ]
aggregate.restype = POINTER(Data)

average = so.average
average.argtypes = [ POINTER(MPHEServer), c_int ]

class MPHEClient(Structure):
    _fields_ = [
        ('params', Params),
        ('crs', Poly),
        ('secretKey', Poly),
        ('decryptionKey', Poly)
    ]

newMPHEClient = so.newMPHEClient
newMPHEClient.restype = POINTER(MPHEClient)

encrypt = so.encrypt
encrypt.argtypes = [ POINTER(Params), POINTER(PolyPair), POINTER(c_double), c_size_t ]
encrypt.restype = POINTER(Data)

# DEBUG
printCiphertext2 = so.printCiphertext2
printCiphertext2.argtypes = [ POINTER(Params), POINTER(Poly), POINTER(Data) ]

import time

def pLuint64(l):
    data = []
    for i in range(l.size):
        data.append(l.data[i])
    
    return data

def pPoly(p):
    coeffs = []
    for i in range(p.size):
        coeff = pLuint64(p.coeffs[i])
        coeffs.append(coeff)
    return coeffs

class pPolyPair:
    def __init__(self, pp):
        self.p0 = pPoly(pp.p0)
        self.p1 = pPoly(pp.p1)

# p_ --> _
def pL_to_L(pL):
    l = Luint64()
    l.size = len(pL)
    l.data = (c_ulonglong * l.size)(*pL)

    return l

def pP_to_Poly(pP):
    coeffs = []
    for coeff in pP:
        c = pL_to_L(coeff)
        coeffs.append(c)

    p = Poly()
    p.size = len(coeffs)
    p.coeffs = (Luint64 * p.size)(*coeffs)

    return p
    
def pPP_to_PolyPair(pPP):
    pp = PolyPair()

    pp.p0 = pP_to_Poly(pPP.p0)
    pp.p1 = pP_to_Poly(pPP.p1)

    return pp

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
    # p.qi.data = (c_ulonglong * len(data1))(*data1)
    # p.qi.size = len(data1)

    # p.pi = Luint64()
    # p.pi.data = (c_ulonglong * len(data2))(*data2)
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
    # print('Server:', server.contents.params, server.contents.crs)
    # CRS = server.contents.crs
    # CRS = genCRS(server).contents
    # crs = []
    # for i in range(server.contents.crs.size):
    #     npCoeff = np.ctypeslib.as_array(CRS.coeffs[i].data, shape=(CRS.coeffs[i].size,))
    #     crs.append(npCoeff.tolist())
    # print('Poly coeffs casted to a list:', len(crs), len(crs[0]))
    # so.printPoly(byref(server.contents.secretKey))

    ### TEST: MPHEClient ###
    # client = newMPHEClient()
    # print('Client:', client.contents.params, client.contents.crs, client.contents.secretKey)

    data = [ 0.0, 1.5, 10000, 4.232425, -3.111111111111 ]
    data_in = (c_double * len(data))(*data)

    params = byref(server.contents.params)
    sk = server.contents.secretKey

    pk = genPublicKey(params, sk)

    # PK to Python
    PK = pPolyPair(pk.contents)
    print('Python PP:', PK, type(PK.p0[0]), PK.p0[0][0])
    pk2 = pPP_to_PolyPair(PK)
    print('ctypes PP:', pk2, pk2.p0, pk2.p0.coeffs, pk2.p0.coeffs.contents.data, pk2.p0.coeffs.contents.data[0])
    print('')

    SK = pPoly(sk)
    print('Python P:', type(SK), type(SK[0]), SK[0][0])
    sk2 = pP_to_Poly(SK)
    print('ctypes PP:', sk2, sk2.coeffs, sk2.coeffs.contents.data, sk2.coeffs.contents.data[0])
    print('')

    # print('\nRAN ZERO\n')
    # # so.printPolyPair(pk)
    ct = encrypt(params, byref(pk2), data_in, len(data))
    print('\nRAN ONCE\n')
    # # so.printPolyPair(pk)
    # # ct = encrypt(params, pk, data_in, len(data))
    # print('\nRAN TWICE\n')

    # # so.printPoly(sk)
    printCiphertext2(params, byref(sk2), ct)

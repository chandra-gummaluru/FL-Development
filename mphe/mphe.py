from ctypes import *
import numpy as np

so = cdll.LoadLibrary('./_mphe.so')

class _Ldouble(Structure):
    _fields_ = [
        ('data', POINTER(c_double)),
        ('size', c_size_t)
    ]

class _Luint64(Structure):
    _fields_ = [
        ('data', POINTER(c_ulonglong)),
        ('size', c_size_t)
    ]

class _Params(Structure):
    _fields_ = [
        ('qi', _Luint64),
        ('pi', _Luint64),

        ('logN', c_int),
        ('logSlots', c_int),
        
        ('scale', c_double),
        ('sigma', c_double)
    ]

newParams = so.newParams
newParams.restype = POINTER(_Params)

class _Poly(Structure):
    _fields_ = [
        ('coeffs', POINTER(_Luint64)),
        ('size', c_size_t)
    ]

newPoly = so.newPoly
newPoly.restype = POINTER(_Poly)

class _PolyPair(Structure):
    _fields_ = [
        ('p0', _Poly),
        ('p1', _Poly)
    ]

genPublicKey = so.genPublicKey
genPublicKey.argtypes = [ POINTER(_Params), POINTER(_Poly) ]
genPublicKey.restype = POINTER(_PolyPair)

class _Ciphertext(Structure):
    _fields_ = [
        ('value', POINTER(_Poly)),
        ('size', c_size_t),
        ('scale', c_double),
        ('isNTT', c_bool)
    ]

newCiphertext = so.newCiphertext
newCiphertext.restype = POINTER(_Ciphertext)

class _Data(Structure):
    _fields_ = [
        ('data', POINTER(_Ciphertext)),
        ('size', c_size_t)
    ]

class _Share(Structure):
    _fields_ = [
        ('data', POINTER(_Poly)),
        ('size', c_size_t)
    ]

class _MPHEServer(Structure):
    _fields_ = [
        ('params', _Params),
        ('crs', _Poly),
        ('secretKey', _Poly),
        
        ('data', _Data),
    ]

_newMPHEServer = so.newMPHEServer
_newMPHEServer.restype = POINTER(_MPHEServer)

_genCRS = so.genCRS
_genCRS.argtypes = [ POINTER(_MPHEServer) ]
_genCRS.restype = POINTER(_Poly)

_colKeySwitch = so.colKeySwitch
_colKeySwitch.argtypes = [ POINTER(_MPHEServer), POINTER(_Share), c_size_t ]

_colKeyGen = so.colKeyGen
_colKeyGen.argtypes = [ POINTER(_MPHEServer), POINTER(_Share), c_size_t ]
_colKeyGen.restype = POINTER(_PolyPair)

_aggregate = so.aggregate
_aggregate.argtypes = [ POINTER(_MPHEServer), POINTER(_Data), c_size_t ]
_aggregate.restype = POINTER(_Data)

_average = so.average
_average.argtypes = [ POINTER(_MPHEServer), c_int ]

class _MPHEClient(Structure):
    _fields_ = [
        ('params', _Params),
        ('crs', _Poly),
        ('secretKey', _Poly),
        ('decryptionKey', _Poly)
    ]

newMPHEClient = so.newMPHEClient
newMPHEClient.restype = POINTER(_MPHEClient)

_encrypt = so.encrypt
_encrypt.argtypes = [ POINTER(_Params), POINTER(_PolyPair), POINTER(c_double), c_size_t ]
_encrypt.restype = POINTER(_Data)

_decrypt = so.decrypt
_decrypt.argtypes = [ POINTER(_Params), POINTER(_Poly), POINTER(_Data) ]
_decrypt.restype = POINTER(_Ldouble)

_genSecretKey = so.genSecretKey
_genSecretKey.argtypes = [ POINTER(_Params) ]
_genSecretKey.restype = POINTER(_Poly)

_genCKGShare = so.genCKGShare
_genCKGShare.argtypes = [ POINTER(_Params), POINTER(_Poly), POINTER(_Poly) ]
_genCKGShare.restype = POINTER(_Share)

_genCKSShare = so.genCKSShare
_genCKSShare.argtypes = [ POINTER(_Params), POINTER(_Poly), POINTER(_Data) ]
_genCKSShare.restype = POINTER(_Share)

### Wrapper classes ###

class Params:
    def __init__(self, _params):
        self.qi = _Conversion.from_luint64(_params.qi)
        self.pi = _Conversion.from_luint64(_params.pi)
        self.logN = _params.logN
        self.logSlots = _params.logSlots
        self.scale = _params.scale
        self.sigma = _params.sigma
    
    def make_structure(self):
        _params = _Params()
        
        _params.qi = _Conversion.to_luint64(self.qi)
        _params.pi = _Conversion.to_luint64(self.pi)
        _params.logN = self.logN
        _params.logSlots = self.logSlots
        _params.scale = self.scale
        _params.sigma = self.sigma

        return _params

class Ciphertext:
    def __init__(self, _ct):
        self.value = [ None ] * _ct.size
        
        for i in range(_ct.size):
            self.value[i] = _Conversion.from_poly(_ct.value[i])
        
        self.scale = _ct.scale
        self.isNTT = _ct.isNTT
    
    def make_structure(self):
        _ct = _Ciphertext()

        value = [ None ] * len(self.value)
        
        for i in range(len(self.value)):
            value[i] = _Conversion.to_poly(self.value[i])
        
        _ct.size = len(value)
        _ct.value = (_Poly * _ct.size)(*value)
        _ct.scale = self.scale
        _ct.isNTT = self.isNTT

        return _ct

class MPHEServer:
    def __init__(self):
        _server_ptr = _newMPHEServer()
        _server = _server_ptr.contents

        self.params = Params(_server.params)
        self.crs = _Conversion.from_poly(_server.crs)
        self.secret_key = _Conversion.from_poly(_server.secretKey)
        self.data = []

class _Conversion:
    # (FYI) Convert to numpy array: https://stackoverflow.com/questions/4355524/getting-data-from-ctypes-array-into-numpy

    def to_list(_l):
        l = [ None ] * _l.size

        for i in range(_l.size):
            l[i] = _l.data[i]
        
        return l

    ### _Luint64

    def from_luint64(_luint64):
        l = [ None ] * _luint64.size

        for i in range(_luint64.size):
            l[i] = _luint64.data[i]
        
        return l

    def to_luint64(l):
        luint64 = _Luint64()

        luint64.size = len(l)
        luint64.data = (c_ulonglong * luint64.size)(*l)

        return luint64

    ### _Ldouble

    def from_ldouble(_ldouble):
        l = [ None ] * _ldouble.size

        for i in range(_ldouble.size):
            l[i] = _ldouble.data[i]
        
        return l

    def to_ldouble(l):
        ldouble = _Ldouble()

        ldouble.size = len(l)
        ldouble.data = (c_ulonglong * ldouble.size)(*l)

        return _ldouble
    
    ### _Poly

    def from_poly(_poly):
        coeffs = [ None ] * _poly.size

        for i in range(_poly.size):
            coeffs[i] = _Conversion.from_luint64(_poly.coeffs[i])
        
        return coeffs
    
    def to_poly(coeffs):
        list_luint64 = [ None ] * len(coeffs)

        for i in range(len(coeffs)):
            list_luint64[i] = _Conversion.to_luint64(coeffs[i])
        
        _poly = _Poly()
        _poly.size = len(list_luint64)
        _poly.coeffs = (_Luint64 * _poly.size)(*list_luint64)

        return _poly

    ### _PolyPair

    def from_polypair(_pp):
        pp = [ None ] * 2

        pp[0] = _Conversion.from_poly(_pp.p0)
        pp[1] = _Conversion.from_poly(_pp.p1)
        
        return pp

    def to_polypair(pp):        
        _pp = _PolyPair()

        if len(pp) != 2:
            print('ERROR: Only a list of size 2 makes a pair (not {})'.format(len(pp)))
            return None

        _pp.p0 = _Conversion.to_poly(pp[0])
        _pp.p1 = _Conversion.to_poly(pp[1])

        return _pp

    ### _Data

    def from_data(_data):
        data = [ None ] * _data.size

        for i in range(_data.size):
            data[i] = Ciphertext(_data.data[i])
        
        return data
    
    def to_data(data):
        list_ciphertext = [ None ] * len(data)

        for i in range(len(data)):
            list_ciphertext[i] = data[i].make_structure()
        
        _data = _Data()
        _data.size = len(list_ciphertext)
        _data.data = (_Ciphertext * _data.size)(*list_ciphertext)

        return _data

# DEBUG
printCiphertext2 = so.printCiphertext2
printCiphertext2.argtypes = [ POINTER(_Params), POINTER(_Poly), POINTER(_Data) ]


if __name__ == '__main__':
    # Instantiate server
    server = MPHEServer()

    data = [ 0.0, 1.5, 10000, 4.232425, -3.111111111111 ]
    print('Original data:', data)
    data_in = (c_double * len(data))(*data)

    params = server.params.make_structure()
    sk = _Conversion.to_poly(server.secret_key)

    # Generate PK and cache on Python
    pk = genPublicKey(byref(params), byref(sk))
    pk = _Conversion.from_polypair(pk.contents)
    pk = _Conversion.to_polypair(pk)

    # Encrypt to CT and cache on Python
    ct = _encrypt(params, byref(pk), data_in, len(data))
    ct = _Conversion.from_data(ct.contents)
    ct = _Conversion.to_data(ct)
    
    printCiphertext2(byref(params), byref(sk), ct)

    data_out = _decrypt(byref(params), byref(sk), ct)
    rec_data = _Conversion.to_list(data_out.contents)
    print('Enc --> Dec:', rec_data)

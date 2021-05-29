from ctypes import *
import numpy as np

### ctypes Structures + Exported Functions from MPHE wrapper of Lattigo ###

# NOTE: the .so file is OS dependent, so should have different versions
# compiled for different systems using Cgo
_so = cdll.LoadLibrary('./mphe/_mphe.so')

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

class _Poly(Structure):
    _fields_ = [
        ('coeffs', POINTER(_Luint64)),
        ('size', c_size_t)
    ]

class _PolyPair(Structure):
    _fields_ = [
        ('p0', _Poly),
        ('p1', _Poly)
    ]

class _Ciphertext(Structure):
    _fields_ = [
        ('value', POINTER(_Poly)),
        ('size', c_size_t),
        ('scale', c_double),
        ('isNTT', c_bool)
    ]

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

_newMPHEServer = _so.newMPHEServer
_newMPHEServer.restype = POINTER(_MPHEServer)

_genCRS = _so.genCRS
_genCRS.argtypes = [ POINTER(_Params) ]
_genCRS.restype = POINTER(_Poly)

_colKeySwitch = _so.colKeySwitch
_colKeySwitch.argtypes = [ POINTER(_Params), POINTER(_Data), POINTER(_Share), c_size_t ]
_colKeySwitch.restype = POINTER(_Data)

_colKeyGen = _so.colKeyGen
_colKeyGen.argtypes = [ POINTER(_Params), POINTER(_Poly), POINTER(_Poly), POINTER(_Share), c_size_t ]
_colKeyGen.restype = POINTER(_PolyPair)

_aggregate = _so.aggregate
_aggregate.argtypes = [ POINTER(_Params), POINTER(_Data), c_size_t ]
_aggregate.restype = POINTER(_Data)

_mulByConst = _so.mulByConst
_mulByConst.argtypes = [ POINTER(_Params), POINTER(_Data), c_double ]
_mulByConst.restype = POINTER(_Data)

class _MPHEClient(Structure):
    _fields_ = [
        ('params', _Params),
        ('crs', _Poly),
        ('secretKey', _Poly),
        ('decryptionKey', _Poly)
    ]

_newMPHEClient = _so.newMPHEClient
_newMPHEClient.restype = POINTER(_MPHEClient)

_encryptFromPk = _so.encryptFromPk
_encryptFromPk.argtypes = [ POINTER(_Params), POINTER(_PolyPair), POINTER(c_double), c_size_t ]
_encryptFromPk.restype = POINTER(_Data)

_encryptFromSk = _so.encryptFromSk
_encryptFromSk.argtypes = [ POINTER(_Params), POINTER(_Poly), POINTER(c_double), c_size_t ]
_encryptFromSk.restype = POINTER(_Data)

_decrypt = _so.decrypt
_decrypt.argtypes = [ POINTER(_Params), POINTER(_Poly), POINTER(_Data) ]
_decrypt.restype = POINTER(_Ldouble)

_genSecretKey = _so.genSecretKey
_genSecretKey.argtypes = [ POINTER(_Params) ]
_genSecretKey.restype = POINTER(_Poly)

_genCKGShare = _so.genCKGShare
_genCKGShare.argtypes = [ POINTER(_Params), POINTER(_Poly), POINTER(_Poly) ]
_genCKGShare.restype = POINTER(_Share)

_genCKSShare = _so.genCKSShare
_genCKSShare.argtypes = [ POINTER(_Params), POINTER(_Poly), POINTER(_Data) ]
_genCKSShare.restype = POINTER(_Share)

### Wrapper Classes (pickle-able) ###

class Params:
    def __init__(self, _params):
        self.qi = _Conversion.from_luint64(_params.qi)
        self.pi = _Conversion.from_luint64(_params.pi)
        self.logN = _params.logN
        self.logSlots = _params.logSlots
        self.scale = _params.scale
        self.sigma = _params.sigma
    
    # So we can send to Lattigo
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
    
    # So we can send to Lattigo
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

# Server that has Multi-Party Homomorphic Encryption functionality
class MPHEServer:
    def __init__(self):
        _server_ptr = _newMPHEServer()
        _server = _server_ptr.contents

        self.params = Params(_server.params)
        self.crs = _Conversion.from_poly(_server.crs)
        self.secret_key = _Conversion.from_poly(_server.secretKey)
        self.data = []  # NOTE: always have this as decryptable by secret_key
    
    def encrypt(self, data):
        params = self.params.make_structure()
        sk = _Conversion.to_poly(self.secret_key)

        data_ptr = (c_double * len(data))(*data)
        enc_data = _encryptFromSk(byref(params), byref(sk), data_ptr, len(data))

        self.data = _Conversion.from_data(enc_data.contents)

        return self.data
    
    def decrypt(self):
        params = self.params.make_structure()
        sk = _Conversion.to_poly(self.secret_key)
        ct = _Conversion.to_data(self.data)

        dec_data = _decrypt(byref(params), byref(sk), byref(ct))
        dec_data = _Conversion.to_list(dec_data.contents)

        return dec_data

    def gen_crs(self):
        params = self.params.make_structure()

        crs = _genCRS(byref(params))
        self.crs = _Conversion.from_poly(crs.contents)

        return self.crs
    
    def col_key_gen(self, ckg_shares):
        params = self.params.make_structure()
        sk = _Conversion.to_poly(self.secret_key)
        crs = _Conversion.to_poly(self.crs)
        shares_ptr = _Conversion.to_ptr(ckg_shares, _Conversion.to_share, _Share)
        
        cpk = _colKeyGen(byref(params), byref(sk), byref(crs), shares_ptr, len(ckg_shares))

        return _Conversion.from_polypair(cpk.contents)

    def col_key_switch(self, agg, cks_shares):
        params = self.params.make_structure()
        data = _Conversion.to_data(agg)
        shares_ptr = _Conversion.to_ptr(cks_shares, _Conversion.to_share, _Share)

        switched_data = _colKeySwitch(byref(params), byref(data), shares_ptr, len(cks_shares))
        self.data = _Conversion.from_data(switched_data.contents)

    def aggregate(self, updates):
        params = self.params.make_structure()
        data_ptr = _Conversion.to_ptr(updates, _Conversion.to_data, _Data)

        agg = _aggregate(byref(params), data_ptr, len(updates))

        return _Conversion.from_data(agg.contents)

    def average(self, n):
        params = self.params.make_structure()
        data = _Conversion.to_data(self.data)

        avg_data = _mulByConst(byref(params), byref(data), 1/n)
        self.data = _Conversion.from_data(avg_data.contents)

    # DEBUG: Decrypts its data then prints contents
    def print_data(self):
        params = self.params.make_structure()
        sk = _Conversion.to_poly(self.secret_key)
        ct = _Conversion.to_data(self.data)

        dec_data = _decrypt(byref(params), byref(sk), byref(ct))
        dec_data = _Conversion.to_list(dec_data.contents)

        print('Decrypted SERVER data:\n\t', dec_data)

# Client that has Multi-Party Homomorphic Encryption functionality
class MPHEClient:
    def __init__(self):
        _client_ptr = _newMPHEClient()
        _client = _client_ptr.contents
        
        self.params = Params(_client.params)
        self.crs = []
        self.secret_key = []
        self.decryption_key = []

        # EXTRA: for demonstration only
        self.data = np.array([ 0.0, 0.0 ])
        self.update = np.array([ 0.0, 0.0])
    
    def define_scheme(self, params, dk):
        self.params = params
        self.decryption_key = dk

    def gen_key(self):
        params = self.params.make_structure()

        sk = _genSecretKey(byref(params))
        self.secret_key = _Conversion.from_poly(sk.contents)

    def encrypt(self, public_key, data):
        params = self.params.make_structure()
        pk = _Conversion.to_polypair(public_key)

        data_ptr = (c_double * len(data))(*data)
        enc_data = _encryptFromPk(byref(params), byref(pk), data_ptr, len(data))

        return _Conversion.from_data(enc_data.contents)

    def decrypt(self, data):
        params = self.params.make_structure()
        sk = _Conversion.to_poly(self.decryption_key)
        ct = _Conversion.to_data(data)

        dec_data = _decrypt(byref(params), byref(sk), byref(ct))
        dec_data = _Conversion.to_list(dec_data.contents)

        return dec_data
    
    def gen_ckg_share(self):
        params = self.params.make_structure()
        sk = _Conversion.to_poly(self.secret_key)
        crs = _Conversion.to_poly(self.crs)

        ckg_share = _genCKGShare(byref(params), byref(sk), byref(crs))

        return _Conversion.from_share(ckg_share.contents)
    
    def gen_cks_share(self, agg):
        params = self.params.make_structure()
        sk = _Conversion.to_poly(self.secret_key)
        data = _Conversion.to_data(agg)

        cks_share = _genCKSShare(byref(params), byref(sk), byref(data))

        return _Conversion.from_share(cks_share.contents)

# Performs conversion between Structures (which contain pointers) to pickle-able classes
class _Conversion:
    # (FYI) Convert to numpy array: https://stackoverflow.com/questions/4355524/getting-data-from-ctypes-array-into-numpy

    # Generic array type Structure to list

    def to_list(_l):
        l = [ None ] * _l.size

        for i in range(_l.size):
            l[i] = _l.data[i]
        
        return l

    def to_list_with_conv(_l, conv):
        l = [ None ] * _l.size

        for i in range(_l.size):
            l[i] = conv(_l.data[i])
        
        return l

    def to_ptr(l, conv, t):
        lt = [ None ] * len(l)

        for i in range(len(l)):
            lt[i] = conv(l[i])
        
        return (t * len(lt))(*lt)

    ### _Luint64 (list of uint64)

    def from_luint64(_luint64):
        return _Conversion.to_list(_luint64)

    def to_luint64(l):
        luint64 = _Luint64()

        luint64.size = len(l)
        luint64.data = (c_ulonglong * luint64.size)(*l)

        return luint64

    ### _Ldouble (list of double)

    def from_ldouble(_ldouble):
        return _Conversion.to_list(_ldouble)

    def to_ldouble(l):
        ldouble = _Ldouble()

        ldouble.size = len(l)
        ldouble.data = (c_ulonglong * ldouble.size)(*l)

        return _ldouble
    
    ### _Poly (list of Coefficients (Luint64))

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

    ### _PolyPair (list[2] of Poly)

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

    ### _Share (list of Poly)

    def from_share(_share):        
        return _Conversion.to_list_with_conv(_share, _Conversion.from_poly)

    def to_share(share):
        list_poly = [ None ] * len(share)

        for i in range(len(share)):
            list_poly[i] = _Conversion.to_poly(share[i])
        
        _share = _Share()
        _share.size = len(list_poly)
        _share.data = (_Poly * _share.size)(*list_poly)

        return _share

    ### _Data (list of Ciphertext)

    def from_data(_data):
        return _Conversion.to_list_with_conv(_data, Ciphertext)
    
    def to_data(data):
        list_ciphertext = [ None ] * len(data)

        for i in range(len(data)):
            list_ciphertext[i] = data[i].make_structure()
        
        _data = _Data()
        _data.size = len(list_ciphertext)
        _data.data = (_Ciphertext * _data.size)(*list_ciphertext)

        return _data

### Network Communication Simulation ###

import pickle

def simulate_network_comm(data):
    pdata = pickle.dumps(data)
    return pickle.loads(pdata)

### MPHE Simulation Test ###

if __name__ == '__main__':
    ## Initialization ##

    server = MPHEServer()
    server.encrypt([ 0.0, 0.0, 1.0, -1.0 ])

    params = server.params
    secret_key = server.secret_key

    # Network Communication (0)
    params = simulate_network_comm(params)
    secret_key = simulate_network_comm(secret_key)

    client1 = MPHEClient()
    client1.define_scheme(params, secret_key)
    client1.update = np.array([ 0.0, 1.0 , 1.0, 0.0])

    client2 = MPHEClient()
    client2.define_scheme(params, secret_key)
    client2.update = np.array([ -1.0, 0.0, 1.0, 0.0 ])

    # DEBUG: Initial model
    server.print_data()

    ## Simulate MPHE Iterations ##

    max_iters = 3

    for i in range(max_iters):
        print('\nITERATION {}\n'.format(i))

        ## Server sends ecnrypted model to Clients ##

        encrypted_model = server.data
        crs = server.gen_crs()

        ct = encrypted_model[0].value

        # Network Communication (1)
        encrypted_model = simulate_network_comm(encrypted_model)
        crs = simulate_network_comm(crs)

        ## Clients intialize current encryption ##

        client1.crs = crs
        client2.crs = crs

        client1.gen_key()
        client2.gen_key()

        ## Collective Key Generation ##

        ckg_shares = []
        ckg_shares.append(client1.gen_ckg_share())
        ckg_shares.append(client2.gen_ckg_share())

        # Network Communication (2)
        ckg_shares = simulate_network_comm(ckg_shares)

        cpk = server.col_key_gen(ckg_shares)

        # Network Communication (3)
        cpk = simulate_network_comm(cpk)

        ## Clients Decrypt + Train ##

        client1.data = client1.decrypt(encrypted_model)
        client2.data = client2.decrypt(encrypted_model)

        client1.data = (np.array(client1.data) + client1.update).tolist()
        client2.data = (np.array(client2.data) + client2.update).tolist()

        ## Clients send encrypted updates to Server ##

        updates = []
        updates.append(client1.encrypt(cpk, client1.data))
        updates.append(client2.encrypt(cpk, client2.data))

        # Network Communication (4)
        updates = simulate_network_comm(updates)

        ## Aggregate updates ##

        agg = server.aggregate(updates)

        # Network Communication (5)
        agg = simulate_network_comm(agg)

        ## Collective Key Switching ##

        cks_shares = []
        cks_shares.append(client1.gen_cks_share(agg))
        cks_shares.append(client2.gen_cks_share(agg))

        # Network Communication (6)
        cks_shares = simulate_network_comm(cks_shares)

        server.col_key_switch(agg, cks_shares)

        ## Average updates post aggregation ##
        
        server.average(len(cks_shares))

        # DEBUG: Verify model is updated as expected
        server.print_data()
    
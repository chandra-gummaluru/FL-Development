import mphe_go

class Params:
    def __init__(self):
        self.qi = []    # []uint64
        self.pi = []    # []uint64
        self.logN = 0
        self.logSlots = 0
        self.scale = 0.0
        self.sigma = 0.0

class Poly:
    def __init__(self):
        self.coeffs = [ [] ]    # [][]uint64

class PolyPair:
    def __init__(self):
        self.p0 = Poly()
        self.p1 = Poly()

class Ciphertext:
    def __init__(self):
        self.value = []     # []Poly()
        self.scale = 0.0
        self.isNTT = False

class Data:
    def __init__(self):
        self.data = []  # []Ciphertext

class Share:
    def __init__(self):
        self.data = []  # []Poly

class MPHEServer:
    def __init__(self):
        self.params = Params()
        self.crs = Poly()
        self.secret_key = Poly()
        self.data = Data()
    
    def ColKeySwitch(self, ciphertext = Data(), cks_shares = [ ]):
        # ciphertext: Data
        # cks_shares: []Share
        pass
    
    def Aggregate(self, ciphertexts = [ [] ]):
        # ciphertexts: []Data
        return []   # Data

    def Average(self, n = 1)
        # n = len(cks_shares)
        pass

    def GenCRS(self):
        return self.crs

    def ColKeyGen(self, ckg_shares = [ ]):
        # ckg_shares: []Share (ASSUME: len(Share.data) == 1)
        return Poly()

class MPHEClient:
    def __init__(self):
        self.params = Params()
        self.crs = Poly()
        self.secret_key = Poly()
        self.decryption_key = Poly()

    def Decrypt(self, ciphertext = []):
        return []   # []float
    
    def Encrypt(self, cpk = Poly(), data = []):
        # data: []float
        return []   # []Ciphertext

    def GenKey(self):
        pass
    
    def GenCKGShare(self):
        return Poly()
    
    def GenCKSShare(self, ciphertext = []):
        # ciphertext: []Ciphertext
        return Poly()

# NOTE: members are not private so Setters/Getters are not defined,
# but feel free to assign them directly...
# eg: Client.decryption_key = Server.secret_key

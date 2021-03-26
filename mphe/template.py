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

class Ciphertext:
    def __init__(self):
        self.value = []     # []Poly()
        self.scale = 0.0
        self.isNTT = False

class MPHEServer:
    def __init__(self):
        self.params = Params()
        self.crs = Poly()
        self.encrypted_model = []   # []Ciphertext
        self.secret_key = Poly()
    
    def ColKeySwitch(self, ciphertext = [], cks_shares = []):
        # ciphertext: []Ciphertext
        # cks_shares: []Poly
        pass
    
    def Aggregate(self, ciphertexts = [ [] ]):
        # ciphertexts: [][]Ciphertext
        return []   # []Ciphertext

    def Average(self, n = 1)
        # n = len(cks_shares)
        pass

    def GenCRS(self):
        return self.crs

    def ColKeyGen(self, ckg_shares = []):
        # ckg_shares: []Poly
        return Poly()

class MPHEClient:
    def __init__(self):
        self.params = Params()
        self.crs = Poly()
        self.decryption_key = Poly()
        self.secret_key = Poly()

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

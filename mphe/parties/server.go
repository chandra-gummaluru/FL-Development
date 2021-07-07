package parties

import (
	"fmt"
	"github.com/ldsec/lattigo/v2/ckks"
	"github.com/ldsec/lattigo/v2/dckks"
	"github.com/ldsec/lattigo/v2/ring"
	"github.com/ldsec/lattigo/v2/utils"
)

type server struct {
	params			*ckks.Parameters
	crs				*ring.Poly
	crs_gen			*ring.UniformSampler
	evaluator		ckks.Evaluator

	ciphertext		*ckks.Ciphertext
	secret_key		*ckks.SecretKey

	cks_protocol	*dckks.CKSProtocol
	cks_share		dckks.CKSShare

	ckg_protocol	*dckks.CKGProtocol
	ckg_share		dckks.CKGShare
}

func NewServer(params *ckks.Parameters, value complex128) server {
	// Server will generate Common Reference Strings (CRS)
	lattigoPRNG, err := utils.NewKeyedPRNG([]byte{'l', 'a', 't', 't', 'i', 'g', 'o'})
	if err != nil {
		panic(err)
	}
	ringQP, _ := ring.NewRing(1<<params.LogN(), append(params.Qi(), params.Pi()...))

	// Secret Key Generation: this is the target collectively switched key
	keygen := ckks.NewKeyGenerator(params)
	secret_key := keygen.GenSecretKey()

	// Server only ever holds encrypted data
	encoder := ckks.NewEncoder(params)
	encryptor := ckks.NewEncryptorFromSk(params, secret_key)
	plaintext := encoder.EncodeNew([]complex128{value}, params.LogSlots())

	// Collective Key Switching will be done on the server
	cks_protocol := dckks.NewCKSProtocol(params, 3.19)

	// Collective Key Generation will be done via the server
	ckg_protocol := dckks.NewCKGProtocol(params)

	// Populate Server instance
	s := server {
		params: params,
		crs_gen: ring.NewUniformSampler(lattigoPRNG, ringQP),
		evaluator: ckks.NewEvaluator(params),

		ciphertext: encryptor.EncryptNew(plaintext),
		secret_key: secret_key,

		cks_protocol: cks_protocol,
		cks_share: cks_protocol.AllocateShare(),

		ckg_protocol: ckg_protocol,
		ckg_share: ckg_protocol.AllocateShares(),
	}

	return s
}

// Perform Collective Key Swtching given client CKS Shares
func (s server) ColKeySwitch(ciphertext *ckks.Ciphertext, shares []dckks.CKSShare) {
	// ASSUME: server's secret_key was also used in creating the cpk
	cks_combined := s.cks_protocol.AllocateShare()

	// Create combined h = \sum(hi)
	shares = append(shares, s.cks_share)

	for _, share := range shares {
		s.cks_protocol.AggregateShares(share, cks_combined, cks_combined)
	}

	// Perform key switching
	s.cks_protocol.KeySwitch(cks_combined, ciphertext, s.ciphertext)

	if DEBUG {
		fmt.Printf("(SERVER) Performed Collective Key Switching\n")
	}
}

// Perform Collective Key Generation (create Collective Public Key) given client CKG Shares
func (s server) ColKeyGen(crs *ring.Poly, shares []dckks.CKGShare) *ckks.PublicKey {
	// ASSUME: all shares where generated with the given CRS
	ckg_combined := s.ckg_protocol.AllocateShares()
	pk := ckks.NewPublicKey(s.params)

	// Create combined p0 = \sum(p0,i)
	s.ckg_share = s.ckg_protocol.AllocateShares()
	s.ckg_protocol.GenShare(s.secret_key.Get(), crs, s.ckg_share)

	shares = append(shares, s.ckg_share)

	for _, share := range shares {
		s.ckg_protocol.AggregateShares(share, ckg_combined, ckg_combined)
	}

	// Perform public key generation
	s.ckg_protocol.GenPublicKey(ckg_combined, crs, pk)

	if DEBUG {
		fmt.Printf("(SERVER) Performed Collective Public Key Generation\n")
	}

	return pk
}

// Generate a Common Reference String (CRS) for the current iteration
func (s *server) GetCRS() *ring.Poly {
	s.crs = s.crs_gen.ReadNew()

	if DEBUG {
		fmt.Printf("(SERVER) Generated CRS\n")
	}

	return s.crs
}

// Retrieve encrypted model
func (s server) GetModel() *ckks.Ciphertext {
	return s.ciphertext
}

// Retrieve the Server's key which will serve as the known model decryption key
func (s server) GetKey() *ckks.SecretKey {
	return s.secret_key
}

// Aggregate encrypted updates from clients
func (s server) Aggregate(ciphertexts []*ckks.Ciphertext) *ckks.Ciphertext {
	// ERROR: no ciphertexts to aggregate
	if len(ciphertexts) == 0 {
		return nil
	}

	// Aggregate all ciphertexts
	aggregate := ciphertexts[0]

	for _, ciphertext := range ciphertexts[1:] {
		s.evaluator.Add(aggregate, ciphertext, aggregate)
	}

	if DEBUG {
		fmt.Printf("(SERVER) Aggregated Updates\n")
	}

	return aggregate
}

// Average aggregate updates
func (s *server) Average(num_updates int) {
	s.evaluator.MultByConst(s.ciphertext, 1.0 / float64(num_updates), s.ciphertext)
}

/* DEBUG */

func (s server) PrintCurrentModel() {
	decrypter := ckks.NewDecryptor(s.params, s.secret_key)
	plaintext := decrypter.DecryptNew(s.ciphertext)

	encoder := ckks.NewEncoder(s.params)
	value := encoder.Decode(plaintext, s.params.LogSlots())[0]

	v := s.ciphertext.Element.Value()
	fmt.Printf("Cipher text size: %v, %v, %v, %v\n", len(v), len(v[0].Coeffs), len(v[0].Coeffs[0]), v[0].Coeffs[0][0])
	fmt.Printf("(SERVER) Current Model is %v\n", value)
}

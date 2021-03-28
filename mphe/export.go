package main

/*
#include <stdbool.h>
#include <stddef.h>

typedef struct {
	long long unsigned int* data;
	size_t size;
} Luint64;

// Params
typedef struct {
	Luint64 qi;
	Luint64 pi;

    int logN;
	int logSlots;
	
	double scale;
	double sigma;
} Params;

// Poly
typedef struct {
	Luint64* coeffs;
	size_t size;
} Poly;

// PolyPair
typedef struct {
	Poly p0;
	Poly p1;
} PolyPair;

// Share
typedef struct {
	Poly* data;
	size_t size;
} Share;

// Ciphertext
typedef struct {
	Poly* value;
	size_t size;

	double scale;
	bool isNTT;
} Ciphertext;

// Data
typedef struct {
	Ciphertext* data;
	size_t size;
} Data;

// MPHEServer
typedef struct {
	Params params;
	Poly crs;
	Poly secretKey;
	Data data;
} MPHEServer;

// MPHEClient
typedef struct {
	Params params;
	Poly crs;
	Poly secretKey;
	Poly decryptionKey;
} MPHEClient;
*/
import "C"
import "unsafe"
import "github.com/ldsec/lattigo/v2/ckks"
import "github.com/ldsec/lattigo/v2/dckks"
import "github.com/ldsec/lattigo/v2/ring"
import "github.com/ldsec/lattigo/v2/utils"
import "fmt"
import "reflect"

var PARAMS *ckks.Parameters = ckks.DefaultParams[ckks.PN12QP109]
var SECRET_KEY *ckks.SecretKey = ckks.NewKeyGenerator(PARAMS).GenSecretKey()
var VALUE complex128 = complex(10.0, 5.0)

var ENCODER ckks.Encoder = ckks.NewEncoder(PARAMS)
var ENCRYPTOR ckks.Encryptor = ckks.NewEncryptorFromSk(PARAMS, SECRET_KEY)
var DECRYPTOR ckks.Decryptor = ckks.NewDecryptor(PARAMS, SECRET_KEY)
var PLAINTEXT *ckks.Plaintext = ENCODER.EncodeNew([]complex128{VALUE}, PARAMS.LogSlots())
var CIPHERTEXT *ckks.Ciphertext = ENCRYPTOR.EncryptNew(PLAINTEXT)

//export mpheTest
func mpheTest() {
	mpheSimulate()
}

//export newParams
func newParams() *C.Params {
	// HARDCODED: Retrieve Default CKKS Params
	p := ckks.DefaultParams[ckks.PN12QP109]

    return convParams(p)
}

//export newPoly
func newPoly() *C.Poly {
	zero := ckks.DefaultParams[ckks.PN14QP438].NewPolyQ()

	return convPoly(zero)
}

//export newCiphertext
func newCiphertext() *C.Ciphertext {
	fmt.Printf("Ciphertext Original Value: %v\n", VALUE)
	return convCiphertext(CIPHERTEXT)
}

/// MPHE Server

//export newMPHEServer
func newMPHEServer() *C.MPHEServer {
	server := (*C.MPHEServer)(C.malloc(C.sizeof_MPHEServer))

	// HARDCODED: CKKS Security Parameters
	server.params = *convParams(PARAMS)

	// Generate CRS
	server.crs = *genCRS(server)

	// Generate SecretKey
	keyGen := ckks.NewKeyGenerator(PARAMS)
	secretKey := keyGen.GenSecretKey()
	server.secretKey = *convPoly(secretKey.Get())

	return server
}

//export genCRS
func genCRS(server *C.MPHEServer) *C.Poly {
	params := convCKKSParams(&server.params)

	lattigoPRNG, err := utils.NewKeyedPRNG([]byte{'l', 'a', 't', 't', 'i', 'g', 'o'})
	if err != nil {
		panic(err)
	}
	ringQP, _ := ring.NewRing(1<<params.LogN(), append(params.Qi(), params.Pi()...))
	
	crsGen := ring.NewUniformSampler(lattigoPRNG, ringQP)
	crs := crsGen.ReadNew()

	return convPoly(crs)
}

//export colKeySwitch
func colKeySwitch(server *C.MPHEServer, data *C.Data, cksShares *C.Share, cksSize C.size_t) {
	// Convert to Go slices
	cts := convSckksCiphertext(data)
	shares := convSSRingPoly(cksShares, cksSize)
	tshares := transpose(shares)

	// Key switch all ciphertexts
	ciphertexts := make([]*ckks.Ciphertext, int(data.size))

	for i, ct := range cts {
		// Create CKSProtocol + Server share
		params := convCKKSParams(&server.params)
		cksProtocol := dckks.NewCKSProtocol(params, 3.19)
		serverShare := cksProtocol.AllocateShare()

		// Create combined h = \sum{hi}
		cksCombined := cksProtocol.AllocateShare()

		// Compute combined h = \sum{hi}
		sharesForCT := tshares[i]
		sharesForCT = append(sharesForCT, serverShare)

		for _, share := range sharesForCT {
			cksProtocol.AggregateShares(share, cksCombined, cksCombined)
		}

		// Perform keyswitching
		serverCT := new(ckks.Ciphertext)
		cksProtocol.KeySwitch(cksCombined, ct, serverCT)
		ciphertexts[i] = serverCT
	}

	// Populate server with key switched data (array of ciphertext)
	server.data = *convData(ciphertexts)
}

//export colKeyGen
func colKeyGen(server *C.MPHEServer, ckgShares *C.Share, ckgSize C.size_t) *C.PolyPair {
	// Create CKG Protocol + Server share
	params := convCKKSParams(&server.params)
	ckgProtocol := dckks.NewCKGProtocol(params)

	secretKey := ckks.NewSecretKey(params)
	secretKey.Set(convRingPoly(&server.secretKey))
	crs := convRingPoly(&server.crs)
	
	serverShare := ckgProtocol.AllocateShares()
	ckgProtocol.GenShare(secretKey.Get(), crs, serverShare)

	// Create combined p0 = \sum{p0_i}
	ckgCombined := ckgProtocol.AllocateShares()

	// Compute combined p0
	shares := convSSRingPoly(ckgShares, ckgSize)	// ASSUME: ckgSize x 1

	for	i := 0 ; i < int(ckgSize) ; i++ {
		ckgProtocol.AggregateShares(shares[i][0], ckgCombined, ckgCombined)
	}

	// Generate public key
	cpk := ckks.NewPublicKey(params)
	ckgProtocol.GenPublicKey(ckgCombined, crs, cpk)
	
	return convPolyPair(cpk.Get())
}

//export aggregate
func aggregate(server *C.MPHEServer, datas *C.Data, datasSize C.size_t) *C.Data {
	// ERROR: no ciphertexts to aggregate
	if int(datasSize) == 0 {
		return nil
	}

	// Get ciphertexts
	cts := convSSckksCiphertext(datas, datasSize)

	// Compute aggregate
	aggregate := make([]*ckks.Ciphertext, int(server.data.size))
	aggregate = cts[0]

	params := convCKKSParams(&server.params)
	evaluator := ckks.NewEvaluator(params)

	for _, ct := range cts[1:] {
		for i, ciphertext := range ct {
			evaluator.Add(aggregate[i], ciphertext, aggregate[i])
		}
	}

	return convData(aggregate)
}

//export average
func average(server *C.MPHEServer, n C.int) {
	N := float64(n)

	// Instantiate evaluator
	params := convCKKSParams(&server.params)
	evaluator := ckks.NewEvaluator(params)
	
	// Normalize each ciphertext making up its data
	ct := convSckksCiphertext(&server.data)
	for i := 0 ; i < len(ct) ; i++ {
		evaluator.MultByConst(ct[i], 1.0 / N, ct[i])
	}

	// Update server's data
	server.data = *convData(ct)
}

/// MPHE Client

//export newMPHEClient
func newMPHEClient() *C.MPHEClient {
	client := (*C.MPHEClient)(C.malloc(C.sizeof_MPHEClient))

	// HARDCODED: CKKS Security Parameters
	client.params = *convParams(PARAMS)

	return client
}

//export encrypt
func encrypt(parms *C.Params, pk *C.PolyPair, array *C.double, arraySize C.size_t) *C.Data {
	params := convCKKSParams(parms)
	encoder := ckks.NewEncoder(params)

	// fmt.Printf("ENTERED GO ENCRYPT\n")
	publicKey := ckks.NewPublicKey(params)
	publicKey.Set(convS2RingPoly(pk))
	// fmt.Printf("Set the public key\n")
	encryptor := ckks.NewEncryptorFromPk(params, publicKey)

	// Encrypt the array element-wise
	size := int(arraySize)
	list := (*[1<<30]C.double)(unsafe.Pointer(array))[:size:size]

	cts := make([]*ckks.Ciphertext, size)
	for i, elem := range list {
		val := complex(float64(elem), 0.0)
		pt := encoder.EncodeNew([]complex128{val}, params.LogSlots())
		// c := encryptor.EncryptNew(pt)
		// fmt.Printf("value to encrypt is %v\n", val)
		cts[i] = encryptor.EncryptNew(pt)
	}

	// parms = convParams(params)
	// pk = convPolyPair(publicKey.Get())

	// data := convData(cts)
	// return data

	return convData(cts)
}

/* DEBUG */

//export printParams
func printParams(params *C.Params) {
	p := convCKKSParams(params)

	fmt.Printf("Reconstructed params: %+v\n", p)
}

//export printPoly
func printPoly(p *C.Poly) {
	r := convRingPoly(p)

	fmt.Printf("Reconstructed poly: %+v\n", reflect.TypeOf(r))
}

//export printPolyPair
func printPolyPair(pp *C.PolyPair) {
	rpp := convS2RingPoly(pp)

	fmt.Printf("Reconstructed polyPair: %+v\n", reflect.TypeOf(rpp))
}

//export printCiphertext
func printCiphertext(c *C.Ciphertext) {
	cc := convCKKSCiphertext(c)
	pt := DECRYPTOR.DecryptNew(cc)
	v := ENCODER.Decode(pt, PARAMS.LogSlots())

	fmt.Printf("Reconstruced ciphertext: %v, %d\n", v[0], len(v))
}

//export printCiphertext2
func printCiphertext2(parms *C.Params, sk *C.Poly, data *C.Data) {
	cts := convSckksCiphertext(data)
	
	params := convCKKSParams(parms)
	secretKey := ckks.NewSecretKey(params)
	secretKey.Set(convRingPoly(sk))
	decryptor := ckks.NewDecryptor(params, secretKey)
	encoder := ckks.NewEncoder(params)

	vals := make([]float64, len(cts))
	for i, cc := range cts {
		pt := decryptor.DecryptNew(cc)
		v := encoder.Decode(pt, params.LogSlots())
		vals[i] = real(v[0])
	}

	fmt.Printf("Reconstruced ciphertext: %v\n", vals)
}

//export genPublicKey
func genPublicKey(parms *C.Params, sk *C.Poly) *C.PolyPair {
	params := convCKKSParams(parms)
	keyGen := ckks.NewKeyGenerator(params)

	secretKey := new(ckks.SecretKey)
	rsk := convRingPoly(sk)
	secretKey.Set(rsk)

	publicKey := keyGen.GenPublicKey(secretKey)
	pk := convPolyPair(publicKey.Get())

	// parms = convParams(params)
	// sk = convPoly(secretKey.Get())

	return pk
}

/* HELPER: Conversion between C and Go structs */

/// Luint64

// []uint64 --> Luint64
func convLuint64(vals []uint64) C.Luint64 {
	list := (*C.Luint64)(C.malloc(C.sizeof_Luint64))

	list.data = (*C.ulonglong)(&vals[0])
	list.size = C.size_t(len(vals))

	return *list
}

// Luint64 --> []uint64
func convSuint64(list C.Luint64) []uint64 {
	// fmt.Printf("List Luint64 is: %v\n", unsafe.Pointer(list.data))
	size := int(list.size)
	// fmt.Printf("Size is: %v\n", size)
	vals := (*[1 << 30]uint64)(unsafe.Pointer(list.data))[:size:size]
	// fmt.Printf("done\n")
	return vals
}

/// Params

// *ckks.Parameters --> *C.Params
func convParams(p *ckks.Parameters) *C.Params {
	params := (*C.Params)(C.malloc(C.sizeof_Params))

	// Populate struct
	params.qi = convLuint64(p.Qi())
	params.pi = convLuint64(p.Pi())

	params.logN = C.int(p.LogN())
	params.logSlots = C.int(p.LogSlots())

	params.scale = C.double(p.Scale())
	params.sigma = C.double(p.Sigma())

    return params
}

// *C.Params --> *ckks.Parameters
func convCKKSParams(params *C.Params) *ckks.Parameters {
	// Create Moduli struct wrapping slices qi, pi
	m := ckks.Moduli{
		Qi: convSuint64(params.qi),
		Pi: convSuint64(params.pi),
	}

	// Create and populate Params
	p, err := ckks.NewParametersFromModuli(uint64(params.logN), &m)
	
	if err != nil {
		fmt.Printf("C.Params built wrong: %v\n", err)
		return nil
	}

	p.SetLogSlots(uint64(params.logSlots))
	p.SetScale(float64(params.scale))
	p.SetSigma(float64(params.sigma))

	return p
}

/// Poly

// *ring.Poly --> *C.Poly
func convPoly(r *ring.Poly) *C.Poly {
	p := (*C.Poly)(C.malloc(C.sizeof_Poly))

	// Retrieve each coeff in a slice of C.Luint64
	coeffs := make([]C.Luint64, len(r.Coeffs))
	for i, coeff := range r.Coeffs {
		c := convLuint64(coeff)
		coeffs[i] = c
	}

	// Populate C.Poly
	p.coeffs = (*C.Luint64)(&coeffs[0])
	p.size = C.size_t(len(coeffs))

	return p
}

// *C.Poly --> *ring.Poly
func convRingPoly(p *C.Poly) *ring.Poly {
	// Extract coeffs as []Luint64
	size := int(p.size)
	list := (*[1<<30]C.Luint64)(unsafe.Pointer(p.coeffs))[:size:size]
	
	// Extract []uint64 from Luint64 to create [][]uint64
	coeffs := make([][]uint64, size)
	for i, coeff := range list {
		// fmt.Printf("(%d) RingPoly: %v, coeff: %v\n", i, p, &coeff)
		c := convSuint64(coeff)
		coeffs[i] = c
	}

	// Populate ring.Poly
	r := new(ring.Poly)
	r.Coeffs = coeffs

	return r
}

/// PolyPair

// [2]*ring.Poly --> *C.PolyPair
func convPolyPair(rpp [2]*ring.Poly) *C.PolyPair {
	pp := (*C.PolyPair)(C.malloc(C.sizeof_PolyPair))

	pp.p0 = *convPoly(rpp[0])
	pp.p1 = *convPoly(rpp[1])

	return pp
}

// *C.PolyPair --> [2]*ring.Poly
func convS2RingPoly(pp *C.PolyPair) [2]*ring.Poly {
	var rpp [2]*ring.Poly
	// fmt.Printf("PK: %v, ", pp)
	// fmt.Printf("PK.p0: %v, PK.p1: %v\n", &pp.p0, &pp.p1)
	rpp[0] = convRingPoly(&pp.p0)
	rpp[1] = convRingPoly(&pp.p1)

	return rpp
}

/// Ciphertext

// *ckks.Ciphertext --> *C.Ciphertext
func convCiphertext(cc *ckks.Ciphertext) *C.Ciphertext {
	c := (*C.Ciphertext)(C.malloc(C.sizeof_Ciphertext))

	// Retrieve each polynomial making up the Ciphertext
	value := make([]C.Poly, len(cc.Element.Value()))
	for i, val := range cc.Element.Value() {
		value[i] = *convPoly(val)
	}

	// Populate C.Ciphertext
	c.value = (*C.Poly)(&value[0])
	c.size = C.size_t(len(value))
	c.scale = C.double(cc.Element.Scale())
	c.isNTT = C.bool(cc.Element.IsNTT())

	return c
}

// *C.Ciphertext --> *ckks.Ciphertext
func convCKKSCiphertext(c *C.Ciphertext) *ckks.Ciphertext {
	size := int(c.size)
	list := (*[1<<30]C.Poly)(unsafe.Pointer(c.value))[:size:size]

	// Extract []*ringPoly from []C.Poly
	value := make([]*ring.Poly, size)
	for i, poly := range list {
		v := convRingPoly(&poly)
		value[i] = v
	}

	// Populate ckks.Ciphertext
	cc := new(ckks.Ciphertext)
	cc.Element = new(ckks.Element)
	
	cc.Element.SetValue(value)
	cc.Element.SetScale(float64(c.scale))
	cc.Element.SetIsNTT(bool(c.isNTT))

	return cc
}

/// Data

// []*ckks.Ciphertext --> *C.Data
func convData(sct []*ckks.Ciphertext) *C.Data {
	data := (*C.Data)(C.malloc(C.sizeof_Data))

	// Retrieve pointer to slice
	ciphertexts := make([]C.Ciphertext, len(sct))
	for i, ct := range sct {
		ciphertexts[i] = *convCiphertext(ct)
	}

	data.data = (*C.Ciphertext)(&ciphertexts[0])
	data.size = C.size_t(len(sct))

	return data
}

// *C.Data --> []*ckks.Ciphertext
func convSckksCiphertext(data *C.Data) []*ckks.Ciphertext {
	size := int(data.size)
	cts := (*[1<<30]C.Ciphertext)(unsafe.Pointer(data.data))[:size:size]

	// Extract []*ckks.Ciphertext from []C.Ciphertext
	cct := make([]*ckks.Ciphertext, size)
	for i, ciphertext := range cts {
		c := convCKKSCiphertext(&ciphertext)
		cct[i] = c
	}

	return cct
}

// (*C.Data, C.size_t) --> [][]*ckks.Ciphertext
func convSSckksCiphertext(datas *C.Data, datasSize C.size_t) [][]*ckks.Ciphertext {
	size := int(datasSize)
	data := (*[1<<30]C.Data)(unsafe.Pointer(datas))[:size:size]

	// Extract [][]*ckks from []C.Data
	ccts := make([][]*ckks.Ciphertext, size)
	for i, ct := range data {
		ccts[i] = convSckksCiphertext(&ct)
	}

	return ccts
}

/// Share

// *C.Share --> []*ringPoly
func convSRingPoly(share *C.Share) []*ring.Poly {
	size := int(share.size)
	list := (*[1<<30]C.Poly)(unsafe.Pointer(share.data))[:size:size]

	// Extract []*ringPoly from []C.Poly
	polys := make([]*ring.Poly, size)
	for i, poly := range list {
		polys[i] = convRingPoly(&poly)
	}

	return polys
}

// (*C.Share, N C.size_t) --> [][]*ring.Poly (N rows, D cols)
func convSSRingPoly(shares *C.Share, sharesSize C.size_t) [][]*ring.Poly {
	size := int(sharesSize)
	list := (*[1<<30]C.Share)(unsafe.Pointer(shares))[:size:size]
	
	// Extract []([]*ring.Poly) from []C.Share
	ssring := make([][]*ring.Poly, size)
	for i, share := range list {
		ssring[i] = convSRingPoly(&share)
	}

	// TODO: Error-check that all shares have the same number of polynomials
	// NOTE: in theory, one share per ciphertext

	return ssring
}

/* HELPER */

func transpose(slice [][]*ring.Poly) [][]*ring.Poly {
    xl := len(slice[0])
    yl := len(slice)
    result := make([][]*ring.Poly, xl)
    for i := range result {
        result[i] = make([]*ring.Poly, yl)
    }
    for i := 0; i < xl; i++ {
        for j := 0; j < yl; j++ {
            result[i][j] = slice[j][i]
        }
    }
    return result
}

package main

/*
#include <stdbool.h>
#include <stddef.h>

typedef struct {
	double* data;
	size_t size;
} Ldouble;

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
import (
	"fmt"
	"unsafe"

	"github.com/ldsec/lattigo/v2/ckks"
	"github.com/ldsec/lattigo/v2/dckks"
	"github.com/ldsec/lattigo/v2/ring"
	"github.com/ldsec/lattigo/v2/utils"
)

// Hardcoded security parameters
var LOGN uint64 = uint64(4)
var LOGSLOTS uint64 = uint64(3)
var SCALE float64 = float64(1 << 30)
var LOGMODULI ckks.LogModuli = ckks.LogModuli{
	LogQi: []uint64{35, 60, 60},
	LogPi: []uint64{30},
}
var SMUDGE float64 = 3.19

/// MPHE Server

//export newMPHEServer
func newMPHEServer() *C.MPHEServer {
	server := (*C.MPHEServer)(C.malloc(C.sizeof_MPHEServer))

	// HARDCODED: CKKS Security Parameters
	PARAMS, _ := ckks.NewParametersFromLogModuli(LOGN, &LOGMODULI)
	PARAMS.SetScale(SCALE)
	PARAMS.SetLogSlots(LOGSLOTS)

	server.params = *convParams(PARAMS)

	// Generate CRS
	server.crs = *genCRS(&server.params)

	// Generate SecretKey
	keyGen := ckks.NewKeyGenerator(PARAMS)
	secretKey := keyGen.GenSecretKey()
	server.secretKey = *convPoly(secretKey.Get())

	return server
}

//export genCRS
func genCRS(parms *C.Params) *C.Poly {
	params := convCKKSParams(parms)

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
func colKeySwitch(parms *C.Params, data *C.Data, cksShares *C.Share, cksSize C.size_t) *C.Data {
	// Convert to Go slices
	cts := convSckksCiphertext(data)
	shares := convSSRingPoly(cksShares, cksSize)
	tshares := transpose(shares)

	// Key switch all ciphertexts
	ciphertexts := make([]*ckks.Ciphertext, int(data.size))

	for i, ct := range cts {
		// Create CKSProtocol + Server share
		params := convCKKSParams(parms)
		cksProtocol := dckks.NewCKSProtocol(params, SMUDGE)
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
		ciphertexts[i] = ckks.NewCiphertext(params, 1, params.MaxLevel(), params.Scale())
		cksProtocol.KeySwitch(cksCombined, ct, ciphertexts[i])
	}

	// Populate server with key switched data (array of ciphertext)
	return convData(ciphertexts)
}

//export colKeyGen
func colKeyGen(sparams *C.Params, ssk *C.Poly, scrs *C.Poly, ckgShares *C.Share, ckgSize C.size_t) *C.PolyPair {
	// Create CKG Protocol + Server share
	params := convCKKSParams(sparams)
	ckgProtocol := dckks.NewCKGProtocol(params)

	secretKey := ckks.NewSecretKey(params)
	secretKey.Set(convRingPoly(ssk))
	crs := convRingPoly(scrs)
	
	serverShare := ckgProtocol.AllocateShares()
	ckgProtocol.GenShare(secretKey.Get(), crs, serverShare)

	// Create combined p0 = \sum{p0_i}
	ckgCombined := ckgProtocol.AllocateShares()

	// Compute combined p0
	shares := convSSRingPoly(ckgShares, ckgSize)	// ASSUME: ckgSize x 1
	shares = append(shares, []*ring.Poly{serverShare})

	for	i := 0 ; i < len(shares) ; i++ {
		ckgProtocol.AggregateShares(dckks.CKGShare(shares[i][0]), ckgCombined, ckgCombined)
	}

	// Generate public key
	cpk := ckks.NewPublicKey(params)
	ckgProtocol.GenPublicKey(ckgCombined, crs, cpk)
	
	return convPolyPair(cpk.Get())
}

//export aggregate
func aggregate(parms *C.Params, datas *C.Data, datasSize C.size_t) *C.Data {
	// ERROR: no ciphertexts to aggregate
	if int(datasSize) == 0 {
		return nil
	}

	// Get ciphertexts
	cts := convSSckksCiphertext(datas, datasSize)

	// Compute aggregate
	aggregate := cts[0]

	params := convCKKSParams(parms)
	evaluator := ckks.NewEvaluator(params)

	for _, ct := range cts[1:] {
		for i, ciphertext := range ct {
			evaluator.Add(aggregate[i], ciphertext, aggregate[i])
		}
	}

	return convData(aggregate)
}

//export mulByConst
func mulByConst(parms *C.Params, data *C.Data, cte C.double) *C.Data {
	Cte := float64(cte)

	// Instantiate evaluator
	params := convCKKSParams(parms)
	evaluator := ckks.NewEvaluator(params)
	
	// Multiply each ciphertext making up its data
	ct := convSckksCiphertext(data)
	for i := 0 ; i < len(ct) ; i++ {
		evaluator.MultByConst(ct[i], Cte, ct[i])
	}
	
	return convData(ct)
}

/// MPHE Client

//export newMPHEClient
func newMPHEClient() *C.MPHEClient {
	client := (*C.MPHEClient)(C.malloc(C.sizeof_MPHEClient))

	// HARDCODED: CKKS Security Parameters
	PARAMS, _ := ckks.NewParametersFromLogModuli(LOGN, &LOGMODULI)
	PARAMS.SetScale(SCALE)
	PARAMS.SetLogSlots(LOGSLOTS)
	
	client.params = *convParams(PARAMS)

	return client
}

//export encryptFromPk
func encryptFromPk(parms *C.Params, pk *C.PolyPair, array *C.double, arraySize C.size_t) *C.Data {
	params := convCKKSParams(parms)
	encoder := ckks.NewEncoder(params)

	publicKey := ckks.NewPublicKey(params)
	publicKey.Set(convS2RingPoly(pk))
	encryptor := ckks.NewEncryptorFromPk(params, publicKey)

	// Encrypt the array element-wise
	size := int(arraySize)
	list := (*[1<<30]C.double)(unsafe.Pointer(array))[:size:size]

	cts := make([]*ckks.Ciphertext, size)
	for i, elem := range list {
		val := complex(float64(elem), 0.0)
		pt := encoder.EncodeNew([]complex128{val}, params.LogSlots())
		cts[i] = encryptor.EncryptNew(pt)
	}

	return convData(cts)
}

//export encryptFromSk
func encryptFromSk(parms *C.Params, sk *C.Poly, array *C.double, arraySize C.size_t) *C.Data {
	params := convCKKSParams(parms)
	encoder := ckks.NewEncoder(params)

	secretKey := ckks.NewSecretKey(params)
	secretKey.Set(convRingPoly(sk))
	encryptor := ckks.NewEncryptorFromSk(params, secretKey)

	// Encrypt the array element-wise
	size := int(arraySize)
	list := (*[1<<30]C.double)(unsafe.Pointer(array))[:size:size]

	cts := make([]*ckks.Ciphertext, size)
	for i, elem := range list {
		val := complex(float64(elem), 0.0)
		pt := encoder.EncodeNew([]complex128{val}, params.LogSlots())
		cts[i] = encryptor.EncryptNew(pt)
	}

	return convData(cts)
}

//export decrypt
func decrypt(parms *C.Params, sk *C.Poly, data *C.Data) *C.Ldouble {
	params := convCKKSParams(parms)
	encoder := ckks.NewEncoder(params)

	secretKey := ckks.NewSecretKey(params)
	secretKey.Set(convRingPoly(sk))
	decryptor := ckks.NewDecryptor(params, secretKey)

	// Decrypt the array element-wise
	cts := convSckksCiphertext(data)
	values := make([]C.double, int(data.size))

	for i, ct := range cts {
		pt := decryptor.DecryptNew(ct)
		v := encoder.Decode(pt, params.LogSlots())[0]
		values[i] = C.double(real(v))
	}
	
	// Populate C.Ldouble
	array := (*C.Ldouble)(C.malloc(C.sizeof_Ldouble))

	array.data = (*C.double)(&values[0])
	array.size = C.size_t(len(values))

	return array
}

//export genSecretKey
func genSecretKey(parms *C.Params) *C.Poly {
	params := convCKKSParams(parms)

	// Generate SecretKey
	keyGen := ckks.NewKeyGenerator(params)
	secretKey := keyGen.GenSecretKey()

	return convPoly(secretKey.Get())
}

//export genCKGShare
func genCKGShare(parms *C.Params, sk *C.Poly, crs *C.Poly) *C.Share {
	params := convCKKSParams(parms)
	ckgProtocol := dckks.NewCKGProtocol(params)

	ckgShare := ckgProtocol.AllocateShares()
	ckgProtocol.GenShare(convRingPoly(sk), convRingPoly(crs), ckgShare)
	
	return convShare([]*ring.Poly{ckgShare})
}

//export genCKSShare
func genCKSShare(parms *C.Params, sk *C.Poly, data *C.Data) *C.Share {
	params := convCKKSParams(parms)
	cksProtocol := dckks.NewCKSProtocol(params, SMUDGE)

	zero := params.NewPolyQ()
	secretKey := ckks.NewSecretKey(params)
	secretKey.Set(convRingPoly(sk))
	
	cts := convSckksCiphertext(data)
	cksShares := make([]*ring.Poly, len(cts))
	for i, ct := range cts {
		cksShares[i] = cksProtocol.AllocateShare()
		cksProtocol.GenShare(secretKey.Get(), zero, ct, cksShares[i])
	}

	return convShare(cksShares)
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
	size := int(list.size)
	vals := (*[1 << 30]uint64)(unsafe.Pointer(list.data))[:size:size]

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

// *C.Share --> []*ring.Poly
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

// []*ring.Poly --> *C.Share
func convShare(polys []*ring.Poly) *C.Share {
	share := (*C.Share)(C.malloc(C.sizeof_Share))
	
	rps := make([]C.Poly, len(polys))
	for i, poly := range polys {
		rps[i] = *convPoly(poly)
	}

	share.data = (*C.Poly)(&rps[0])
	share.size = C.size_t(len(rps))

	return share
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

/* HELPER: Miscallaneous */

// Source: https://gist.github.com/tanaikech/5cb41424ff8be0fdf19e78d375b6adb8
func transpose(slice [][]*ring.Poly) [][]*ring.Poly {
    xl := len(slice[0])
    yl := len(slice)

	// Initialize
    result := make([][]*ring.Poly, xl)
    for i := range result {
        result[i] = make([]*ring.Poly, yl)
    }

	// Tranpose
    for i := 0; i < xl; i++ {
        for j := 0; j < yl; j++ {
            result[i][j] = slice[j][i]
        }
    }

    return result
}

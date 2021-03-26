package main

/*
typedef struct {
	long long unsigned int* data;
	size_t size;
} Luint64;

typedef struct {
	Luint64 qi;
	Luint64 pi;

    int logN;
	int logSlots;
	
	double scale;
	double sigma;
} Params;
*/
import "C"
import "github.com/ldsec/lattigo/v2/ckks"

//export mpheTest
func mpheTest() {
	mpheSimulate()
}

//export newParams
func newParams() *C.Params {
	params := (*C.Params)(C.malloc(C.sizeof_Params))

	// HARDCODED: Retrieve Default CKKS Params
	p := ckks.DefaultParams[ckks.PN14QP438]

	// Populate struct
	params.qi = newLuint64(p.Qi())
	params.pi = newLuint64(p.Pi())

	params.logN = C.int(p.LogN())
	params.logSlots = C.int(p.LogSlots())

	params.scale = C.double(p.Scale())
	params.sigma = C.double(p.Sigma())

    return params
}

/* HELPER */

// []uint64 --> Luint64
func newLuint64(vals []uint64) C.Luint64 {
	list := (*C.Luint64)(C.malloc(C.sizeof_Luint64))

	list.data = (*C.ulonglong)(&vals[0])
	list.size = C.size_t(len(vals))

	return *list
}

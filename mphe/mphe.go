package main

import (
	"fmt"
	"mphe/parties"
	"github.com/ldsec/lattigo/v2/ckks"
	"github.com/ldsec/lattigo/v2/dckks"
)

func mpheSimulate() {
	/* Initialization */

	// Encryption scheme parameters
	params := ckks.DefaultParams[ckks.PN12QP109]

	// Initialize Server
	server := parties.NewServer(params, complex(0.0, 0.0))

	// Initialize Clients
	client1 := parties.NewClient(params, server.GetKey(), "CLIENT 1", complex(1.0, 0.0))
	client2 := parties.NewClient(params, server.GetKey(), "CLIENT 2", complex(0.0, 2.0))

	// DEBUG: Display initial model
	server.PrintCurrentModel()

	/* Simulate MPHE iterations */

	maxIters := 3

	for i := 0 ; i < maxIters ; i++ {
		fmt.Printf("\nITERATION %d\n\n", i)

		/* Server sends encrypted model to Clients */

		encryptedModel := server.GetModel()
		crs := server.GetCRS()

		/* Clients Decrypt + Train */

		client1.TrainModel(encryptedModel, crs)
		client2.TrainModel(encryptedModel, crs)

		/* Collective Key Generation */

		client1.GenKey()
		client2.GenKey()

		ckgShares := []dckks.CKGShare{}
		ckgShares = append(ckgShares, client1.GetCKGShare())
		ckgShares = append(ckgShares, client2.GetCKGShare())

		cpk := server.ColKeyGen(crs, ckgShares)

		/* Clients send encrypted update to Server */

		updates := []*ckks.Ciphertext{}
		updates = append(updates, client1.ColEnc(cpk))
		updates = append(updates, client2.ColEnc(cpk))

		/* Aggregate updates */

		aggregate := server.Aggregate(updates)

		/* Collective Key Switching */

		cksShares := []dckks.CKSShare{}
		cksShares = append(cksShares, client1.GetCKSShare(aggregate))
		cksShares = append(cksShares, client2.GetCKSShare(aggregate))

		server.ColKeySwitch(aggregate, cksShares)

		/* Average updates post aggregation */

		// NOTE: this assumes the averaging is just a scale of however we aggregated
		server.Average(len(cksShares))

		// DEBUG: Verify model is updated as expected
		server.PrintCurrentModel()
	}
}

func main() {
	mpheSimulate()
}

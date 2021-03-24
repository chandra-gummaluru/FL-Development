package main

import (
	"fmt"
	"mphe/parties"
	"github.com/ldsec/lattigo/v2/ckks"
	"github.com/ldsec/lattigo/v2/dckks"
)

func main() {
	/* Initialization */

	// Encryption scheme parameters
	params := ckks.DefaultParams[ckks.PN14QP438]

	// Initialize Server
	server := parties.NewServer(params, complex(0.0, 0.0))

	// Initialize Clients
	client1 := parties.NewClient(params, server.GetKey(), "CLIENT 1", complex(1.0, 0.0))
	client2 := parties.NewClient(params, server.GetKey(), "CLIENT 2", complex(0.0, 2.0))

	// DEBUG: Display initial model
	server.PrintCurrentModel()

	/* Simulate MPHE iterations */

	max_iters := 3

	for i := 0 ; i < max_iters ; i++ {
		fmt.Printf("\nITERATION %d\n\n", i)

		/* Server sends encrypted model to Clients */

		encrypted_model := server.GetModel()
		crs := server.GetCRS()

		/* Clients Decrypt + Train */

		client1.TrainModel(encrypted_model, crs)
		client2.TrainModel(encrypted_model, crs)

		/* Collective Key Generation */

		client1.GenKey()
		client2.GenKey()

		ckg_shares := []dckks.CKGShare{}
		ckg_shares = append(ckg_shares, client1.GetCKGShare())
		ckg_shares = append(ckg_shares, client2.GetCKGShare())

		cpk := server.ColKeyGen(crs, ckg_shares)

		/* Clients send encrypted update to Server */

		updates := []*ckks.Ciphertext{}
		updates = append(updates, client1.ColEnc(cpk))
		updates = append(updates, client2.ColEnc(cpk))

		/* Aggregate updates */

		aggregate := server.Aggregate(updates)

		/* Collective Key Switching */

		cks_shares := []dckks.CKSShare{}
		cks_shares = append(cks_shares, client1.GetCKSShare(aggregate))
		cks_shares = append(cks_shares, client2.GetCKSShare(aggregate))

		server.ColKeySwitch(aggregate, cks_shares)

		/* Average updates post aggregation */

		// NOTE: this assumes the averaging is just a scale of however we aggregated
		server.Average(len(cks_shares))

		// DEBUG: Verify model is updated as expected
		server.PrintCurrentModel()
	}
}

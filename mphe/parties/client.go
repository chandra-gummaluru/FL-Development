package parties

import (
	"fmt"
	"github.com/ldsec/lattigo/v2/ckks"
	"github.com/ldsec/lattigo/v2/dckks"
	"github.com/ldsec/lattigo/v2/ring"
)

type client struct {
	params			*ckks.Parameters
	crs				*ring.Poly
	evaluator		ckks.Evaluator

	keygen			ckks.KeyGenerator
	secret_key		*ckks.SecretKey

	decryption_key	*ckks.SecretKey
	encoder			ckks.Encoder
	decrypter		ckks.Decryptor
	
	cks_protocol 	*dckks.CKSProtocol
	ckg_protocol 	*dckks.CKGProtocol

	// Non Homomorphic Encryption related members
	name			string
	update_value	complex128
	data			complex128
}

func NewClient(params *ckks.Parameters, decryption_key *ckks.SecretKey, name string, value complex128) client {	
	// TODO: create relinearization and rotation keys

	// Populate Client instance
	c := client {
		params: params,
		evaluator: ckks.NewEvaluator(params),

		keygen: ckks.NewKeyGenerator(params),

		decryption_key: decryption_key,
		encoder: ckks.NewEncoder(params),
		decrypter: ckks.NewDecryptor(params, decryption_key),

		cks_protocol: dckks.NewCKSProtocol(params, 3.19),
		ckg_protocol: dckks.NewCKGProtocol(params),

		name: name,
		update_value: value,
	}

	return c
}

// Train current iteration's model
func (c *client) TrainModel(encrypted_model *ckks.Ciphertext, crs *ring.Poly) {
	// Cache current iteration's CRS
	c.crs = crs

	// Decrypt + Decode model
	encoded_model := c.decrypter.DecryptNew(encrypted_model)
	c.data = c.encoder.Decode(encoded_model, c.params.LogSlots())[0]

	// Train model
	if DEBUG {
		fmt.Printf("(%s) Recieved Encrypted Model: %v\n", c.name, c.data)
	}

	c.data += c.update_value

	if DEBUG {
		fmt.Printf("(%s) Trained Encrypted Model: %v\n", c.name, c.data)
	}
}

// Generate Client Secret Key
func (c *client) GenKey() {
	c.secret_key = c.keygen.GenSecretKey()

	if DEBUG {
		fmt.Printf("(%s) Generated New Secret Key: %+v\n", c.name, c.secret_key)
	}
}

// Generate CKG Share for Collective Key Generation (for Collective Public Key)
func (c client) GetCKGShare() dckks.CKGShare {
	ckg_share := c.ckg_protocol.AllocateShares()
	c.ckg_protocol.GenShare(c.secret_key.Get(), c.crs, ckg_share)

	if DEBUG {
		fmt.Printf("(%s) Generated New CKG Share\n", c.name)
	}

	return ckg_share
}

// Perform encryption of current data using the Collective Public Key
func (c client) ColEnc(cpk *ckks.PublicKey) *ckks.Ciphertext {
	plaintext := c.encoder.EncodeNew([]complex128{c.data}, c.params.LogSlots())
	encryptor := ckks.NewEncryptorFromPk(c.params, cpk)

	if DEBUG {
		fmt.Printf("(%s) Encrypted Using Collecitve Public Key: %+v\n", c.name, cpk)
	}

	return encryptor.EncryptNew(plaintext)
}

// Generate CKS Share for Collective Key Switching
func (c client) GetCKSShare(ciphertext *ckks.Ciphertext) dckks.CKSShare {
	zero := c.params.NewPolyQ()
	cks_share := c.cks_protocol.AllocateShare()
	c.cks_protocol.GenShare(c.secret_key.Get(), zero, ciphertext, cks_share)
	
	if DEBUG {
		fmt.Printf("(%s) Generated New CKS Share\n", c.name)
	}

	return cks_share
}


import torch
import torchvision
import torchvision.transforms as transforms
from torch.utils.data import DataLoader
import torch.nn.functional as F
import torch.nn as nn
import numpy as np
from collections import OrderedDict


import numpy as np


class Compressor:
    def __init__(self):
        pass

 
  # compression function takes in dropout rate and random seed.
    # input original model, output compressed model
    def compress(self, decompressed_model, dropout_rate=0.5, random_seed=123):
        compressed_weights = {}
        zero_indices = {}
        # print(model)
        for name, m in decompressed_model.named_children():
            # convert tensor to numpy array
            orig_weights = m.weight.detach().numpy()
            #print(orig_weights.shape)
            # multi-dimensions to 1d
            flattened_orig = orig_weights.ravel()
            # generate random index for locations of zeros
            random_indices = self.random_index(flattened_orig.size, dropout_rate=dropout_rate, random_seed=random_seed)
            # drop zeros
            compressed_flattened_weights = np.delete(flattened_orig, random_indices)
            compressed_weights[name] = {
                'size': flattened_orig.size,
                'shape': orig_weights.shape,
                'weights': compressed_flattened_weights,
                'bias': m.bias
            }
            #print(compressed_flattened_weights.nbytes)
        return compressed_weights
        


           # Reconstruction
    def decompress(self, compressed_model):
        reconstructed_model = OrderedDict()
        for layer in compressed_model:
            shape = compressed_model[layer]['shape']
            new_array = np.zeros(compressed_model[layer]['size'])
            # random seed needs to be the same as what was used in compression
            zero_indices = self.random_index(compressed_model[layer]['size'], random_seed=123)
            count = 0
            z = 0
            for i in range(compressed_model[layer]['size']):
                if z < len(zero_indices) and i == zero_indices[z]:
                    new_array[i] = 0
                    z += 1
                else:
                    new_array[i] = compressed_model[layer]['weights'][i - z]

            # Reshape after for loop is finished
            weight_tensor = torch.tensor(new_array.reshape(shape))
            reconstructed_model[f'{layer}.weight'] = weight_tensor
            reconstructed_model[f'{layer}.bias'] = compressed_model[layer]['bias']
        return reconstructed_model


    def random_index(self, max_range, dropout_rate=0.5, random_seed=123):
        np.random.seed(random_seed)
        random_list = np.random.choice(range(max_range), int(max_range * dropout_rate) , replace=False)
        random_list.sort()
        return random_list 
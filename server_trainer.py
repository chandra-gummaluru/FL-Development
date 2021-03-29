import torch
import torchvision
import torchvision.transforms as transforms
from torch.utils.data import DataLoader

import numpy as np
np.set_printoptions(formatter={'float': lambda x: "{0:0.2f}".format(x)})

import utils
from utils import DEBUG_LEVEL, TERM

debug_level = DEBUG_LEVEL.INFO

import sys, csv

import model1

# Class encapsulating Training program for the Server's model
class ServerTrainer():
    def __init__(self, use_cuda=True):
        # Model
        self.model = model1.Net()

        # Test Data
        self.test_loader = self.load_test_data()
        self.test_acc = [ ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'] ]

        # Enable CUDA
        self.use_cuda = use_cuda
        if self.use_cuda and torch.cuda.is_available():
            self.model = self.model.cuda()

    ### Training Program ###

    # Aggregate updates into a single update
    def aggregate(self, updates):
        # Zero the state
        aggregate_update = self.get_zero_state()

        for key in aggregate_update:
            # Accumulate the updates
            for update in updates:
                aggregate_update[key] += update[key]

            # Average
            aggregate_update[key] /= len(updates)

        return aggregate_update

    # Apply the aggregate update to the model
    def update(self, aggregate_update):
        self.model.load_state_dict(aggregate_update)

        # Compute Accuracy (test)
        self.test_acc.append(self.compute_accuracy(self.test_loader))

        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write('\tEpoch ' + str(len(self.test_acc) - 1) + '\n')
            TERM.write('\tClass Accuracies: {}'.format(100 * np.array(self.test_acc[-1])))

        # Occasionally save current test accuracy
        self.save_to_csv(self.test_acc, './train_curves/server.csv')

    ### Helper Functions ###

    # Creates an zero set of weights
    def get_zero_state(self):
        model = model1.Net()
        # Enable CUDA
        if self.use_cuda and torch.cuda.is_available():
            model = model.cuda()

        state = model.state_dict()

        # Iterate and set all weights to zero
        for key in state:
            state[key] *= 0.0

        return state

    # Load test dataset
    def load_test_data(self):
        composition = transforms.Compose([transforms.ToTensor(), transforms.Normalize((0.5,), (0.5,))])
        test_set = torchvision.datasets.MNIST(root='./data', train=False, download=True, transform=composition)

        return DataLoader(test_set, batch_size=len(test_set.targets), shuffle=False)

    # Compute per class accuracy
    def compute_accuracy(self, data_loader):
        # Cache results for each class
        correct_by_class = torch.zeros(10)
        total_by_class = torch.zeros(10)

        # Enable CUDA
        if self.use_cuda and torch.cuda.is_available():
            correct_by_class = correct_by_class.cuda()
            total_by_class = total_by_class.cuda()

        for inputs, targets in data_loader:
            # Enable CUDA
            if self.use_cuda and torch.cuda.is_available():
                inputs = inputs.cuda()
                targets = targets.cuda()

            # Compute predictions
            with torch.no_grad():
                outputs = self.model(inputs)

            preds = outputs.max(1, keepdim=True)[1]

            # determine the number correct per class.
            labels, counts = torch.unique(targets[(preds.squeeze() == targets).nonzero()], return_counts=True)
            correct_by_class[labels] += counts.float()

            # determine the number per class.
            labels, counts = torch.unique(targets, return_counts=True)
            total_by_class[labels] += counts.float()

        total_by_class[(total_by_class == 0).nonzero()] = 1.0 # TODO: Change this to be an NaN.

        return (correct_by_class / total_by_class).cpu().tolist()

    # Save data to CSV file
    def save_to_csv(self, data, file_path):
        with open(file_path, 'w+', newline='') as csv_file:
            writer = csv.writer(csv_file)
            writer.writerows(data)

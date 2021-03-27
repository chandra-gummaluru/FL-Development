import utils
from utils import DEBUG_LEVEL, COLORS

import torch
import torchvision
import torchvision.transforms as transforms
import torch.nn as nn
from torch.utils.data import DataLoader

import time, csv
import numpy as np

debug_level = DEBUG_LEVEL.INFO

import model1

class ClientTrainer():
    def __init__(self, local_client_digits, use_cuda=True):
        # Hyperparameters
        self.num_epochs = 2
        self.lr = 1e-3
        self.momentum = 0.9
        self.batch_size = 164    #4

        # EXTRA: Cache digits part of this client's dataset
        self.digits = local_client_digits

        composition = transforms.Compose([transforms.ToTensor(), transforms.Normalize((0.5,), (0.5,))])

        # Load MNIST dataset
        train_set = torchvision.datasets.MNIST(root='./data', train=True, download=True, transform=composition)
        test_set = torchvision.datasets.MNIST(root='./data', train=False, download=True, transform=composition)

        # Select relevant subset of samples
        indices = (train_set.targets[..., None] == torch.tensor(local_client_digits)).any(-1).nonzero().squeeze() # Equivalent to np.isin()

        train_set.data = train_set.data[indices]
        train_set.targets = train_set.targets[indices]

        # Wrap in DataLoader
        self.train_loader = DataLoader(train_set, batch_size=self.batch_size, shuffle=True)
        self.test_loader = DataLoader(test_set, batch_size=len(test_set.targets), shuffle=False)

        # Instantiate model
        self.model = model1.Net()

        # Train/Test Curves
        self.train_acc = [ ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'] ]
        self.test_acc = [ ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'] ]

        # Enable CUDA
        self.use_cuda = use_cuda
        if self.use_cuda and torch.cuda.is_available():
            self.model = self.model.cuda()

    ### Training Program ###

    # Load weights from server model
    def load_weights(self, weights):
        self.model.load_state_dict(weights)

    # Compute focused update to send
    def focused_update(self):
        return self.model.state_dict()

    def train(self):
        # Optimization Settings
        criterion = nn.CrossEntropyLoss()
        optimizer = torch.optim.SGD(self.model.parameters(), lr=self.lr, momentum=self.momentum)

        start = time.time()

        for epoch in range(self.num_epochs):
            running_loss = 0.0

            for i, (inputs, targets) in enumerate(self.train_loader):
                # Enable CUDA
                if self.use_cuda and torch.cuda.is_available():
                    inputs = inputs.cuda()
                    targets = targets.cuda()

                # Forward Pass
                outputs = self.model(inputs)
                loss = criterion(outputs, targets)

                # Backward Pass
                loss.backward()
                optimizer.step()
                optimizer.zero_grad()

                # Accumulate the loss
                running_loss += loss.item()

            if debug_level >= DEBUG_LEVEL.INFO:
                print('\tEpoch ' + str(epoch + 1))

            train_acc_list, train_acc  = self.evaluate_accuracy(self.train_loader)
            test_acc_list, test_acc = self.evaluate_accuracy(self.test_loader)
            self.train_acc.append(train_acc_list)
            self.test_acc.append(test_acc_list)

            if debug_level >= DEBUG_LEVEL.INFO:
                np.set_printoptions(precision=3)
                print(COLORS.OKBLUE + '\tTraining Accuracy: ' + str(train_acc) + COLORS.ENDC)
                print(COLORS.OKBLUE + '\tTesting Accuracy: ' + str(test_acc) + COLORS.ENDC)
        end = time.time()

        if debug_level >= DEBUG_LEVEL.INFO:
            print('\t%0.2f minutes' %((end - start) / 60))

        # Save train/test accuracy after training
        self.save_to_csv(self.train_acc, './train_curves/client{}_train.csv'.format(self.digits))
        self.save_to_csv(self.test_acc, './train_curves/client{}_test.csv'.format(self.digits))

    ### Helper Functions ###

    def evaluate_accuracy(self, data_loader):
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

        acc = 100 * correct_by_class.sum() / total_by_class.sum()
        return (correct_by_class / total_by_class).cpu().tolist(), np.array(acc.cpu())

    # Save data to CSV file
    def save_to_csv(self, data, file_path):
        with open(file_path, 'w+', newline='') as csv_file:
            writer = csv.writer(csv_file)
            writer.writerows(data)


# TEST
if __name__ == '__main__':

    trainer = ClientTrainer([1, 2, 3], use_cuda=True)
    trainer.load_weights(trainer.model.state_dict())
    print('Weights loaded successfully!')

    trainer.train()
    print('Model trained successfully!')
    print('Focused update computed successfully!')

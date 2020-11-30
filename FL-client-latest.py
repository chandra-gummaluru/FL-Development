#!/usr/bin/env python
# coding: utf-8

# In[1]:


import torch
import torchvision
import torchvision.transforms as transforms
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.data import DataLoader,TensorDataset
import numpy as np
import time
from torchvision import datasets
import matplotlib.pyplot as plt  # This is python's popular plotting library.
# This is to ensure matplotlib plots inline and does not try to open a new window.
get_ipython().run_line_magic('matplotlib', 'inline')


# In[2]:


class Net(nn.Module):
    def __init__(self):
        super(Net, self).__init__()
        self.conv1 = nn.Conv2d(in_channels=1, out_channels=20,
                               kernel_size=5, stride=1)
        self.conv2 = nn.Conv2d(in_channels=20, out_channels=50,
                               kernel_size=5, stride=1)
        self.fc1 = nn.Linear(in_features=50*4*4, out_features=500)
        self.fc2 = nn.Linear(in_features=500, out_features=10)
    def forward(self, x):
        x = F.relu(self.conv1(x.float()))
        x = F.max_pool2d(x, 2, 2)
        x = F.relu(self.conv2(x)) #do we need to convert to float here as well?
        x = F.max_pool2d(x, 2, 2)
        x = x.view(x.size(0), -1)
        x = F.relu(self.fc1(x))
        x = self.fc2(x)
        return x


# In[48]:


class ML_Client:
    def __init__(self, local_client_digits):
        # load local training data
        trainset = datasets.MNIST(
            root = './data',
            train = True,
            download = False,
            transform = transforms.Compose(
                [transforms.ToTensor(),
                 transforms.Normalize((0.5,), (0.5,))]
            )
        )
        # load local testing data
        testset = datasets.MNIST(
            root = './data',
            train = False,
            download = False,
            transform = transforms.Compose(
                [transforms.ToTensor(),
                 transforms.Normalize((0.5,), (0.5,))]
            )
        )
        testloader = DataLoader(
            testset,
            batch_size = 4,
            shuffle = False
        )

        # select a subset of digits from dataset
        idx = []
        for i in local_client_digits:
            idx_i = (trainset.targets == i).nonzero()[:,0].tolist()
            print("digit %d: %d samples" %(i, len(idx_i)))
            idx += idx_i

        print("number of selected data = {}".format(len(idx)))

        # for some mysterious reason, when i do this, it works, but when i switch to the 4 lines above, it only recognized 1/3 digits??
        trainset.data = trainset.data[idx]
        trainset.targets = trainset.targets[idx]

        # must shuffle data to avoid learning all ones, all twos, all threes in one go
        trainloader = DataLoader(
            trainset,
            batch_size = 4,
            shuffle = True
        )

        self.model = Net()
        self.training_data = trainloader
        self.testing_data = testloader
        self.device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')

    def load_weights(self, weights):
        # weights is a state_dict
        self.model.load_state_dict(weights)

    def train(self):
        # loss function
        criterion = nn.CrossEntropyLoss()
        # optimizer
        optimizer = optim.SGD(self.model.parameters(), lr=0.001, momentum=0.9)

        start = time.time()
        for epoch in range(3): # no. of epochs
            running_loss = 0.0
            for i, data in enumerate(self.training_data, 0):
                # data pixels and labels to GPU if available
                inputs, labels = data[0].to(self.device, non_blocking=True), data[1].to(self.device, non_blocking=True)
                # set the parameter gradients to zero
                optimizer.zero_grad()
                outputs = self.model(inputs)
                loss = criterion(outputs, labels)
                # propagate the loss backward
                loss.backward()
                optimizer.step()
                # print for mini batches
                running_loss += loss.item()
                if i % 10 == 1:  # every 1000 mini batches
                    print('[Epoch %d, %5d Mini Batches] loss: %.3f' %
                          (epoch + 1, i + 1, running_loss/1000))
                    running_loss = 0.0
                    self.evaluate_accuracy()
        end = time.time()
        print('Done Training')
        print('%0.2f minutes' %((end - start) / 60))
        
    def evaluate_accuracy(self):
        correct = 0
        total = 0
        correct_per_digit = np.zeros(10)
        total_per_digit = np.zeros(10)

        with torch.no_grad():
            for i, data in enumerate(self.testing_data):
                inputs, labels = data[0].to(self.device, non_blocking=True), data[1].to(self.device, non_blocking=True)

                # net 1
                outputs = self.model(inputs)
                _, predicted = torch.max(outputs.data, 1)
                total += labels.size(0)
                correct += (predicted == labels).sum().item()

                # compute accuracy per digit label
                for i in range(10):
                    total_per_digit[i] += labels.tolist().count(i)
                    if i in labels:
                        idx = labels.tolist().index(i)
                        correct_per_digit[i] += (predicted[idx] == i).sum().item()

        print('Accuracy of the network on all digits: %0.3f %%' % (100 * correct / total))

        for i in range(10):
            print('Accuracy of the network digit %d: %0.3f %%' % (i, 100 * correct_per_digit[i] / total_per_digit[i]))

        print(correct_per_digit)
        print(total_per_digit)
        print('total trainning batch number: {}'.format(len(trainloader)))


    def get_focused_update(self):
        return self.model.state_dict()
    
    def get_model(self):
        return self.model
    
    def get_training_data(self):
        return self.training_data
    
    def get_testing_data(self):
        return self.testing_data


# In[49]:


# test __init__
client = ML_Client([1,2,3])

model = client.get_model()
for param in model.parameters():
    print(param)
    break

# check if we have the correct dimensions
trainloader = client.get_training_data()
testloader = client.get_testing_data()
for i, data in enumerate(trainloader, 0):
    print("\nselected trainset:")
    print("{} (should be [4, 1, 28, 28])".format(data[0].shape))
    print("{} (should be [4])".format(data[1].shape))
    print(data[1])
    break

for i, data in enumerate(testloader, 0):
    print("\ntestset:")
    print(data[0].shape)
    print(data[1].shape)
    print(data[1])
    break


# In[50]:


# test load_weights
PATH2 = './models/model2' #456
net_sd = torch.load(PATH2)

client.load_weights(net_sd)
loaded_model = client.get_model()
# for param in loaded_model.parameters():
#     print(param)
#     break
    
client.evaluate_accuracy()


# In[51]:


# test train
client.train()
trained_model = client.get_model()
# for param in trained_model.parameters():
#     print(param)
#     break


# In[37]:


# test focused_update
update = client.get_focused_update()
print(update)


# In[38]:


# test evaluate_accuracy
client.evaluate_accuracy()


import matplotlib.pyplot as plt
import pandas as pd
import os

import numpy as np

# Plots each entry in data (blocking for each plot)
def plot_data(df, title, classes=None):
    # Default classes to plot (all of them)
    if classes == None:
        classes = np.arange(10) #df.columns.values

    data = np.array(df.values)[:,classes]

    plt.plot(range(1, data.shape[0] + 1), data)

    plt.xlabel('Iteration')
    plt.ylabel('Accuracy')

    plt.title(title)
    plt.legend(tuple(classes), loc='upper left')

    plt.savefig('./train_curves/{}.png'.format(title), bbox_inches='tight')
    plt.show()
        

if __name__ == '__main__':
    clients = [[3, 5, 7, 9], [0, 1, 8], [2, 4, 6]]

    # Plot server curve
    server_path = './train_curves/server.csv'

    if os.path.exists(server_path):
        df = pd.read_csv(server_path)        
        plot_data(df, 'Server Test Accuracy (per class)')

    # Plot client curves
    for digits in clients:
        train_path = './train_curves/client{}_train.csv'.format(digits)
        test_path = './train_curves/client{}_test.csv'.format(digits)

        # Verify the client exists
        if (not os.path.exists(train_path)) or (not os.path.exists(test_path)):
            continue

        # Plot client's train accuracy curve
        df = pd.read_csv(train_path)
        plot_data(df, 'Client{} Train Accuracy (per class)'.format(digits), classes=digits)

        # Plot client's test accurcay curve
        df = pd.read_csv(test_path)
        plot_data(df, 'Client{} Test Accuracy (per class)'.format(digits))

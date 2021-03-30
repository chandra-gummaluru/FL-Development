import os, csv, sys

import matplotlib
from matplotlib import pyplot as plt
from matplotlib.animation import FuncAnimation

import numpy as np

class Plotter():
    def __init__(self, data_path, interval = 5000):
        self.data_path = data_path
        self.interval = interval

    def plot(self):
        fig = plt.figure()
        ani = FuncAnimation(plt.gcf(), self.animate, interval = self.interval)
        plt.show()

    def animate(self, i):
        data = []
        with open(self.data_path, newline='') as csv_file:
            reader = csv.reader(csv_file)
            for row in reader:
                data.append(row)
            data = np.array(data, dtype=np.float32)
            plt.plot(range(len(data)), data)

# Plot MNIST model curves
def plot_MNIST(data_path):
    data = []
    title = os.path.basename(data_path)
    title = os.path.splitext(title)[0]
    
    with open(data_path, newline='') as csv_file:
        reader = csv.reader(csv_file)
        for row in reader:
            data.append(row)
        data = np.array(data, dtype=np.float32)
    
    plt.plot(range(len(data)), data)

    plt.xlabel('Iteration')
    plt.ylabel('Accuracy')

    plt.title(title)
    plt.legend(tuple(np.arange(10)), loc='best')

    plt.ylim((0, 1))
    plt.grid(True)

    plt.savefig('./train_curves/{}.png'.format(title), bbox_inches='tight')
    plt.show()

# TEST
if __name__ == '__main__':
    data_path = sys.argv[1]

    if len(sys.argv) < 3:
        plot_MNIST(data_path)
    else:
        interval = int(sys.argv[2])

        plotter = Plotter(data_path, interval = interval)
        plotter.plot()

import os, csv, sys

import matplotlib
from matplotlib import pyplot as plt

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
        with open('test.csv', newline='') as csv_file:
            reader = csv.reader(csv_file)
            for row in reader:
                data.append(row)
            data = np.array(data, dtype=np.float32)
            plt.plot(range(len(data)), data)

# TEST
if __name__ == '__main__':
    data_path = sys.argv[1]
    interval = int(sys.argv[2])

    plotter = Plotter(data_path, interval = interval)
    plotter.plot()

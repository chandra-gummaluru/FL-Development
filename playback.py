import sys

import csv
import numpy as np

from matplotlib import pyplot as plt
from matplotlib.animation import FuncAnimation

plt.rcParams['text.usetex'] = True
plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.serif'] = ['Palatino']

class Playback:
    def __init__(self, path, interval):
        self.figure = None
        self.anim = None
        self.running = False
        self.digits = []

        # Cache animation interval
        self.interval = interval
        self.legend = (
            r'0', r'1', r'2', r'3', r'4', r'5', r'6', r'7', r'8', r'9'
        )

        # Read in data
        self.data = []
        with open(path, newline='') as csv_file:
            reader = csv.reader(csv_file)
            for row in reader:
                self.data.append(row)

    def onClick(self, event):
        if self.running:
            self.anim.event_source.stop()
            self.running = False
            print('Paused. Click to start!')
        else:
            self.anim.event_source.start()
            self.running = True
            print('Started animation')

    def animate_server(self):
        self.figure = plt.figure()

        self.figure.canvas.mpl_connect('button_press_event', self.onClick)
        self.running = True

        self.anim = FuncAnimation(plt.gcf(), self.plot_server, interval=self.interval)
        plt.show()
    
    def plot_server(self, i):
        # Retrieve data
        num_pts = min(i, len(self.data))
        data = np.array(self.data[:num_pts], dtype=np.float32)

        if num_pts < 2:
            return

        # Plot data
        plt.plot(range(num_pts), data * 100)

        # Format plot
        plt.title(r'\textbf{Server}: Per Class Accuracy over Time', fontsize=14)
        plt.legend(self.legend, loc='lower right')

        plt.xlabel(r'Iteration', fontsize=10)
        plt.ylabel(r'Accuracy (\%)', fontsize=10)

        plt.xlim((0, num_pts - 1))
        plt.ylim((0, 100))

        ax = self.figure.gca()
        ax.xaxis.get_major_locator().set_params(integer=True)
        plt.yticks((0, 20, 40, 60, 80 , 100))

        plt.grid(True)

    def animate_client(self, digits):
        self.digits = tuple(digits)

        self.figure = plt.figure()

        self.figure.canvas.mpl_connect('button_press_event', self.onClick)
        self.running = True

        self.anim = FuncAnimation(plt.gcf(), self.plot_client, interval=self.interval)
        self.running = True
        plt.show()
    
    def plot_client(self, i):
        # Retrieve data
        num_pts = min(i, len(self.data))
        data = np.array(self.data[:num_pts], dtype=np.float32)

        if num_pts < 2:
            return

        # Plot data
        plt.plot(range(num_pts), data * 100)

        # Format plot
        plt.title(r'\textbf{Client} ' + '{0}: Per Class Accuracy over Time'.format(self.digits), fontsize=14)
        plt.legend(self.legend, loc='lower right')

        plt.xlabel(r'Iteration', fontsize=10)
        plt.ylabel(r'Accuracy (\%)', fontsize=10)

        plt.xlim((0, num_pts - 1))
        plt.ylim((0, 100))

        ax = self.figure.gca()
        ax.xaxis.get_major_locator().set_params(integer=True)
        plt.yticks((0, 20, 40, 60, 80 , 100))

        plt.grid(True)

if __name__ == '__main__':
    SERVER_PATH = './curves/Server_All.csv'  # PARTY 0
    CLIENT_PATHS = [
        './curves/Client[0, 1, 8]_All.csv',
        './curves/Client[2, 4, 6]_All.csv',
        './curves/Client[3, 5, 7, 9]_All.csv'
    ]
    CLIENT_DIGITS = [
        [ 0, 1, 8 ],
        [ 2, 4, 6 ],
        [ 3, 5, 7, 9 ]
    ]

    # Arguments
    PARTY = int(sys.argv[1])
    if len(sys.argv) > 2:
        INTERVAL = float(sys.argv[2])
    else:
        INTERVAL = 1.0 if PARTY == 0 else 0.5

    # Plot
    if PARTY == 0:
        pb = Playback(SERVER_PATH, int(INTERVAL * 1000))
        pb.animate_server()
    else:
        pb = Playback(CLIENT_PATHS[PARTY - 1], int(INTERVAL * 1000))
        pb.animate_client(CLIENT_DIGITS[PARTY - 1])

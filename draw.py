# NOTE: this code will be removed from here!
import redis
import hashlib
import numpy as np
import time
import json
import matplotlib.pyplot as plt

def load_data():
    rdb = redis.StrictRedis()
    data_serialized = rdb.get('relia-time-sink-0')
    data = np.frombuffer(data_serialized, dtype=np.complex64)
    # data_json = open('/tmp/relia-data.json').read()
    # print(hashlib.md5(data_json.encode()).hexdigest())
    # data = json.loads(data_json)
     
    # creating initial data values
    # of x and y
    # x = range(len(data['real']))
    # y_real = [ np.float32(y1) for y1 in data['real'] ]
    # y_imag = [ np.float32(y1) for y1 in data['imag'] ]

    x = range(len(data))
    y_real = data.real
    y_imag = data.imag

    return x, y_real, y_imag
 
# to run GUI event loop
plt.ion()
 
x, y_real, y_imag = load_data()

# here we are creating sub plots
figure, ax = plt.subplots(figsize=(10, 8))
line1, = ax.plot(x, y_real)
line2, = ax.plot(x, y_imag)
 
# setting title
plt.title("RELIA", fontsize=20)
 
# setting x-axis label and y-axis label
plt.xlabel("Tiime")
plt.ylabel("Amplitude")
 
while True:

    x, y_real, y_imag = load_data()
 
    # updating data values
    line1.set_xdata(x)
    line1.set_ydata(y_real)
    line2.set_xdata(x)
    line2.set_ydata(y_imag)
 
    # drawing updated values
    figure.canvas.draw()
 
    # This will run the GUI event
    # loop until all UI events
    # currently waiting have been processed
    figure.canvas.flush_events()
 
    time.sleep(0.1)

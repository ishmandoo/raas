from driver import Encoder, Motor
from time import sleep, time
import pickle 
enc = Encoder()

T = 1.0
dt = 0.01
steps = T / dt

angles = []
start_time = time()
for i in range(steps):
    sleep(dt)
    angles.append(enc.getRadian())
total_time = time() - start_time
print(total_time)
pickle.dump(angles, open( "free_run.p", "wb"))




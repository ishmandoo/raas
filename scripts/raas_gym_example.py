import path_utils
import raas_gym
import numpy as np



print('Creating gym object...')
# Creates and returns Pendulum env object
env_pend = raas_gym.make('Pendulum-v0')

N_steps = 300
s = None
for t in range(N_steps):
    print(f'Step {t}')
    action = np.array([2.0*np.sin(0.05*t)])
    print('\tAction: {}'.format(action))
    s_next, r, done, _ = env_pend.step(action)
    print('\tState: {}, reward: {}'.format(s_next, r))


    s = s_next



print('\nDone!')


#

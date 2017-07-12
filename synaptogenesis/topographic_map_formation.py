"""
Test for topographic map formation using STDP and synaptic rewiring.

http://hdl.handle.net/1842/3997
"""
# Imports
import numpy as np
import pylab

from spinn_utilities.progress_bar import ProgressBar
import time
from pacman.model.constraints.placer_constraints.placer_chip_and_core_constraint import \
    PlacerChipAndCoreConstraint
import spynnaker7.pyNN as sim

import argparse

# Constants
CASE_CORR_AND_REW = 1
CASE_CORR_NO_REW = 2
CASE_REW_NO_CORR = 3

SSP = 1
SSA = 2

DEFAULT_TAU_REFRAC = 5.0
DEFAULT_T_RECORD = 1000
DEFAULT_F_PEAK = 152.8
DEFAULT_NO_INTERATIONS = 3000000
DEFAULT_T_STIM = 20

DEFAULT_SPIKE_SOURCE = SSP

parser = argparse.ArgumentParser(
    description='Test for topographic map formation using STDP and synaptic rewiring'
                ' on SpiNNaker.', formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument("-c", '--case', type=int, choices=[CASE_CORR_AND_REW, CASE_CORR_NO_REW, CASE_REW_NO_CORR],
                    default=CASE_CORR_AND_REW, dest='case',
                    help='an integer controlling the experimental setup')

parser.add_argument('--tau_refract', type=float,
                    default=DEFAULT_TAU_REFRAC, dest='tau_refrac',
                    help='refractory time constant (ms)')

parser.add_argument('--t_record', type=int,
                    default=DEFAULT_T_RECORD, dest='t_record',
                    help='time between retrieval of recordings (ms)')

parser.add_argument('--t_stim', type=int,
                    default=DEFAULT_T_STIM, dest='t_stim',
                    help='time between stimulus location change (ms)')

parser.add_argument('--f_peak', type=float,
                    default=DEFAULT_F_PEAK, dest='f_peak',
                    help='peak input spike rate (Hz)')

parser.add_argument('--no_iterations', type=int,
                    default=DEFAULT_NO_INTERATIONS, dest='no_iterations',
                    help='total number of iterations (or time steps) for the simulation (technically, ms)')

parser.add_argument("-s", '--spike_source', type=int, choices=[SSP, SSA],
                    default=DEFAULT_SPIKE_SOURCE, dest='spike_source',
                    help='choice of input spike source: \n'
                         '[' + str(SSP) + '] poisson spike source \n'
                                          '[' + str(SSA) + '] spike source array'
                    )

parser.add_argument('--no_plot', help="don't display any plots", action="store_true")

parser.add_argument('-o', '--output', type=str, help="name of the numpy archive storing simulation results",
                    dest='filename')

args = parser.parse_args()

case = args.case
print "Case", case, "selected!"

# SpiNNaker setup
start_time = pylab.datetime.datetime.now()

sim.setup(timestep=1.0, min_delay=1.0, max_delay=10)
sim.set_number_of_neurons_per_core("IF_curr_exp", 50)
sim.set_number_of_neurons_per_core("IF_cond_exp", 256 // 13)
sim.set_number_of_neurons_per_core("SpikeSourcePoisson", 256 // 15)
sim.set_number_of_neurons_per_core("SpikeSourceArray", 256 // 8)


# +-------------------------------------------------------------------+
# | Function definitions                                              |
# +-------------------------------------------------------------------+

# Periodic boundaries
# https://github.com/pabogdan/neurogenesis/blob/master/notebooks/neurogenesis-in-numbers/Periodic%20boundaries.ipynb
def distance(x0, x1, grid=np.asarray([16, 16]), type='euclidian'):
    x0 = np.asarray(x0)
    x1 = np.asarray(x1)
    delta = np.abs(x0 - x1)
    delta = np.where(delta > grid * .5, delta - grid, delta)

    if type == 'manhattan':
        return np.abs(delta).sum(axis=-1)
    return np.sqrt((delta ** 2).sum(axis=-1))


# Poisson spike source as from list spike source
# https://github.com/project-rig/pynn_spinnaker_bcpnn/blob/master/examples/modular_attractor/network.py#L115-L148
def poisson_generator(rate, t_start, t_stop):
    n = int((t_stop - t_start) / 1000.0 * rate)
    number = np.ceil(n + 3 * np.sqrt(n))
    if number < 100:
        number = min(5 + np.ceil(2 * n), 100)

    if number > 0:
        isi = np.random.exponential(1.0 / rate, int(number)) * 1000.0
        if number > 1:
            spikes = np.add.accumulate(isi)
        else:
            spikes = isi
    else:
        spikes = np.array([])

    spikes += t_start
    i = np.searchsorted(spikes, t_stop)

    extra_spikes = []
    if len(spikes) == i:
        # ISI buf overrun

        t_last = spikes[-1] + np.random.exponential(1.0 / rate, 1)[0] * 1000.0

        while (t_last < t_stop):
            extra_spikes.append(t_last)
            t_last += np.random.exponential(1.0 / rate, 1)[0] * 1000.0

            spikes = np.concatenate((spikes, extra_spikes))
    else:
        spikes = np.resize(spikes, (i,))

    # Return spike times, rounded to millisecond boundaries
    unique_rounded_times = np.unique(np.array([round(x) for x in spikes]))
    return unique_rounded_times[unique_rounded_times < t_stop]


def generate_rates(s, grid):
    '''
    Function that generates an array the same shape as the input layer so that
    each cell has a value corresponding to the firing rate for the neuron
    at that position.
    '''
    _rates = np.zeros(grid)
    for x in range(grid[0]):
        for y in range(grid[1]):
            _d = distance(s, (x, y), grid)
            _rates[x, y] = f_base + f_peak * np.e ** (
                -_d / (2 * (sigma_stim ** 2)))
    return _rates


def formation_rule(potential_pre, post, sigma, p_form):
    d = distance(potential_pre, post)
    r = np.random.rand()
    p = p_form * (np.e ** (-(d ** 2 / (2 * (sigma ** 2)))))
    if r < p:
        return True
    return False


# Initial connectivity

def generate_initial_connectivity(s, existing_pre, connections, sigma, p, msg):
    # print "|", 256 // 4 * "-", "|"
    # print "|",
    pbar = ProgressBar(total_number_of_things_to_do=N_layer,
                       string_describing_what_being_progressed=msg)
    for postsynaptic_neuron_index in range(N_layer):
        # if postsynaptic_neuron_index % 8 == 0:
        #     print "=",
        pbar.update()
        post = (postsynaptic_neuron_index // n, postsynaptic_neuron_index % n)
        while s[postsynaptic_neuron_index] < s_max:
            potential_pre_index = np.random.randint(0, N_layer)
            pre = (potential_pre_index // n, potential_pre_index % n)
            if potential_pre_index not in existing_pre[
                postsynaptic_neuron_index]:
                if formation_rule(pre, post, sigma, p):
                    s[postsynaptic_neuron_index] += 1
                    existing_pre[postsynaptic_neuron_index].append(
                        potential_pre_index)
                    connections.append((potential_pre_index,
                                        postsynaptic_neuron_index, g_max, 1))
                    # print " |"


# +-------------------------------------------------------------------+
# | General Parameters                                                |
# +-------------------------------------------------------------------+

# Population parameters
model = sim.IF_cond_exp

# Membrane
v_rest = -70  # mV
e_ext = 0  # V
v_thr = -54  # mV
g_max = 0.2
tau_m = 20  # ms
tau_ex = 5  # ms

cell_params = {'cm': 20.0,  # nF
               'i_offset': 0.0,
               'tau_m': 20.0,
               'tau_refrac': args.tau_refrac,
               'tau_syn_E': 5.0,
               'tau_syn_I': 5.0,
               'v_reset': -70.0,
               'v_rest': -70.0,
               'v_thresh': -50.0,
               'e_rev_E': 0.,
               'e_rev_I': -80.
               }

# +-------------------------------------------------------------------+
# | Rewiring Parameters                                               |
# +-------------------------------------------------------------------+
no_iterations = args.no_iterations  # 300000 # 3000000 # 3,000,000 iterations
simtime = no_iterations
# Wiring
n = 16
N_layer = n ** 2
S = (n, n)
# S = (256, 1)
grid = np.asarray(S)

s = (n // 2, n // 2)
s_max = 16
sigma_form_forward = 2.5
sigma_form_lateral = 1
p_form_lateral = 1
p_form_forward = 0.16
p_elim_dep = 0.0245
p_elim_pot = 1.36 * np.e ** -4
f_rew = 10 ** 4  # Hz

# Inputs
f_mean = 20  # Hz
f_base = 5  # Hz
f_peak = args.f_peak  # 152.8  # Hz
sigma_stim = 2  # 2
t_stim = args.t_stim  # 20  # ms
t_record = args.t_record  # ms

# STDP
a_plus = 0.1
b = 1.2
tau_plus = 20.  # ms
tau_minus = 64.  # ms
a_minus = (a_plus * tau_plus * b) / tau_minus

# Reporting

sim_params = {'g_max': g_max,
              't_stim': t_stim,
              'simtime': simtime,
              'f_base': f_base,
              'f_peak': f_peak,
              'sigma_stim': sigma_stim,
              't_record': t_record,
              'cell_params': cell_params,
              'case': args.case
              }

# +-------------------------------------------------------------------+
# | Initial network setup                                             |
# +-------------------------------------------------------------------+
# Need to setup the moving input

if args.spike_source == SSP:
    if case == CASE_REW_NO_CORR:
        rates = np.ones(grid) * f_mean
    else:
        rates = generate_rates(np.random.randint(0, 16, size=2), grid)
    source_pop = sim.Population(N_layer,
                                sim.SpikeSourcePoisson,
                                {'rate': rates.ravel(),
                                 'start': 0,
                                 'duration': simtime
                                 }, label="Poisson spike source")
else:
    if case == CASE_REW_NO_CORR:
        rates = np.ones((grid[0], grid[1], t_record // t_stim)) * f_mean
    else:
        rates = np.zeros((grid[0], grid[1], t_record // t_stim))
    for rate_id in range(t_record // t_stim):
        rates[:, :, rate_id] = generate_rates(np.random.randint(0, 16, size=2),
                                              grid)
    rates = rates.reshape(N_layer, t_record // t_stim)
    spike_times = []
    for _ in range(N_layer):
        spike_times.append([])

    for n_id in range(N_layer):
        for t in range(t_record // t_stim):
            spike_times[n_id].append(poisson_generator(rates[n_id, t], t * t_stim, t_stim * (t + 1)))
        spike_times[n_id] = np.concatenate(spike_times[n_id])
    spikeArray = {'spike_times': spike_times}
    source_pop = sim.Population(N_layer,
                                sim.SpikeSourceArray,
                                spikeArray,
                                label="Array spike source")

ff_s = np.zeros(N_layer)
lat_s = np.zeros(N_layer)

existing_pre_ff = []
existing_pre_lat = []
for _ in range(N_layer):
    existing_pre_ff.append([])
    existing_pre_lat.append([])

init_ff_connections = []
init_lat_connections = []
generate_initial_connectivity(
    ff_s, existing_pre_ff, init_ff_connections,
    sigma_form_forward, p_form_forward,
    "\nGenerating initial feedforward connectivity...")
generate_initial_connectivity(
    lat_s, existing_pre_lat, init_lat_connections,
    sigma_form_lateral, p_form_lateral,
    "\nGenerating initial lateral connectivity...")
print "\n"

# Neuron populations
target_pop = sim.Population(N_layer, model, cell_params, label="TARGET_POP")
# target_pop.set_constraint(PlacerChipAndCoreConstraint(0, 1))
# Connections
# Plastic Connections between pre_pop and post_pop

stdp_model = sim.STDPMechanism(
    timing_dependence=sim.SpikePairRule(tau_plus=tau_plus,
                                        tau_minus=tau_minus),
    weight_dependence=sim.AdditiveWeightDependence(w_min=0, w_max=g_max,
                                                   # A_plus=0.02, A_minus=0.02
                                                   A_plus=a_plus,
                                                   A_minus=a_minus)
)
if case == CASE_CORR_AND_REW or case == CASE_REW_NO_CORR:
    structure_model_w_stdp = sim.StructuralMechanism(stdp_model=stdp_model,
                                                     weight=g_max,
                                                     s_max=s_max * 2,
                                                     grid=grid)
elif case == CASE_CORR_NO_REW:
    structure_model_w_stdp = stdp_model

# structure_model_w_stdp = sim.StructuralMechanism(weight=g_max, s_max=s_max)

ff_projection = sim.Projection(
    source_pop, target_pop,
    sim.FromListConnector(init_ff_connections),
    synapse_dynamics=sim.SynapseDynamics(slow=structure_model_w_stdp),
    label="plastic_ff_projection"
)

lat_projection = sim.Projection(
    target_pop, target_pop,
    sim.FromListConnector(init_lat_connections),
    synapse_dynamics=sim.SynapseDynamics(slow=structure_model_w_stdp),
    label="plastic_lat_projection"
)

# +-------------------------------------------------------------------+
# | Simulation and results                                            |
# +-------------------------------------------------------------------+

# Record neurons' potentials
# target_pop.record_v()

# Record spikes
# if case == CASE_REW_NO_CORR:
source_pop.record()
target_pop.record()

# Run simulation
pre_spikes = []
post_spikes = []

pre_sources = []
pre_targets = []
pre_weights = []
pre_delays = []

post_sources = []
post_targets = []
post_weights = []
post_delays = []

# rates_history = np.zeros((16, 16, simtime // t_stim))
e = None
print "Starting the sim"

no_runs = None
run_duration = None
if args.spike_source == SSP and not case == CASE_REW_NO_CORR:
    no_runs = simtime // t_stim
    run_duration = t_stim
else:
    no_runs = simtime // t_record
    run_duration = t_record

try:
    for run in range(no_runs):
        print "run", run + 1, "of", no_runs
        sim.run(run_duration)
        spike_times = []
        if args.spike_source == SSP:
            if case == CASE_REW_NO_CORR:
                rates = np.ones(grid) * f_mean
            else:
                rates = generate_rates(np.random.randint(0, 16, size=2), grid)
            source_pop.set("rate", rates.ravel())
        else:
            if case == CASE_REW_NO_CORR:
                rates = np.ones((grid[0], grid[1], t_record // t_stim)) * f_mean
            else:
                rates = np.zeros((grid[0], grid[1], t_record // t_stim))
            for rate_id in range(t_record // t_stim):
                rates[:, :, rate_id] = generate_rates(np.random.randint(0, 16, size=2),
                                                      grid)
            rates = rates.reshape(N_layer, t_record // t_stim)
            spike_times = []
            for _ in range(N_layer):
                spike_times.append([])

            for n_id in range(N_layer):
                for t in range(t_record // t_stim):
                    spike_times[n_id].append(poisson_generator(rates[n_id, t], t * t_stim, t_stim * (t + 1)))
                spike_times[n_id] = np.concatenate(spike_times[n_id])
            source_pop.set("spike_times", spike_times)

        # Retrieve data

        # if run * t_stim % t_record == 0:
        if run == no_runs - 1:
            pre_weights.append(
                np.array(ff_projection._get_synaptic_data(False, 'weight')))
            post_weights.append(
                np.array(lat_projection._get_synaptic_data(False, 'weight')))


    pre_spikes = source_pop.getSpikes(compatible_output=True)
    post_spikes = target_pop.getSpikes(compatible_output=True)
    # End simulation on SpiNNaker
    sim.end()
except Exception as e:
    print e
# print("Weights:", plastic_projection.getWeights())
end_time = pylab.datetime.datetime.now()
total_time = end_time - start_time

print "Total time elapsed -- " + str(total_time)


def plot_spikes(spikes, title):
    if spikes is not None:
        f, ax1 = pylab.subplots(1, 1, figsize=(16, 8))
        ax1.set_xlim((0, simtime))
        ax1.scatter([i[1] for i in spikes], [i[0] for i in spikes], s=.2)
        ax1.set_xlabel('Time/ms')
        ax1.set_ylabel('spikes')
        ax1.set_title(title)

    else:
        print "No spikes received"


init_ff_conn_network = np.ones((256, 256)) * np.nan
init_lat_conn_network = np.ones((256, 256)) * np.nan
for source, target, weight, delay in init_ff_connections:
    init_ff_conn_network[int(source), int(target)] = weight
for source, target, weight, delay in init_lat_connections:
    init_lat_conn_network[int(source), int(target)] = weight

suffix = end_time.strftime("_%H%M%S_%d%m%Y")

if args.filename:
    filename = args.filename
else:
    filename = "topographic_map_results" + str(suffix)

np.savez(filename, pre_spikes=pre_spikes,
         post_spikes=post_spikes,
         init_ff_connections=init_ff_conn_network,
         init_lat_connections=init_lat_conn_network,
         final_pre_weights=pre_weights,
         final_post_weights=post_weights,
         simtime=simtime,
         sim_params=sim_params,
         total_time=total_time,
         exception=e)

# Plotting
if not args.no_plot:
    plot_spikes(pre_spikes, "Source layer spikes")
    pylab.show()
    plot_spikes(post_spikes, "Target layer spikes")
    pylab.show()

    f, (ax1, ax2) = pylab.subplots(1, 2, figsize=(16, 8))
    i = ax1.matshow(np.nan_to_num(pre_weights[-1].reshape(256, 256)))
    i2 = ax2.matshow(np.nan_to_num(post_weights[-1].reshape(256, 256)))
    ax1.grid(visible=False)
    ax1.set_title("Feedforward connectivity matrix", fontsize=16)
    ax2.set_title("Lateral connectivity matrix", fontsize=16)
    cbar_ax = f.add_axes([.91, 0.155, 0.025, 0.72])
    cbar = f.colorbar(i2, cax=cbar_ax)
    cbar.set_label("Synaptic conductance - $G_{syn}$", fontsize=16)
    pylab.show()

    f, (ax1, ax2) = pylab.subplots(1, 2, figsize=(16, 8))
    i = ax1.matshow(
        np.nan_to_num(pre_weights[-1].reshape(256, 256)) - np.nan_to_num(
            init_ff_conn_network))
    i2 = ax2.matshow(
        np.nan_to_num(post_weights[-1].reshape(256, 256)) - np.nan_to_num(
            init_lat_conn_network))
    ax1.grid(visible=False)
    ax1.set_title("Diff- Feedforward connectivity matrix", fontsize=16)
    ax2.set_title("Diff- Lateral connectivity matrix", fontsize=16)
    cbar_ax = f.add_axes([.91, 0.155, 0.025, 0.72])
    cbar = f.colorbar(i2, cax=cbar_ax)
    cbar.set_label("Synaptic conductance - $G_{syn}$", fontsize=16)
    pylab.show()

print "Total time elapsed -- " + str(total_time)

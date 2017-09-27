from __future__ import division
from collections import Iterable

import numpy as np
import matplotlib.pyplot as plt
import pylab as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib import cm
from matplotlib.ticker import LinearLocator, FormatStrFormatter
import scipy
import scipy.stats as stats
from glob import glob
from pprint import pprint as pp
from synaptogenesis.function_definitions import *
from analysis_functions_definitions import *
from argparser import *

paths = []
for file in args.path:
    if "*" in file:
        globbed_files = glob(file)
        for globbed_file in globbed_files:
            if "npz" in globbed_file:
                paths.append(globbed_file)
    else:
        paths.append(file)
for file in paths:
    try:
        start_time = plt.datetime.datetime.now()
        print "\n\nAnalysing file", str(file)
        data = np.load(file)
        simdata = np.array(data['sim_params']).ravel()[0]

        if 'case' in simdata:
            print "Case", simdata['case'], "analysis"
        else:
            print "Case unknown"
        simtime = int(data['simtime'])
        post_spikes = data['post_spikes']

        ff_last = data['final_pre_weights']
        lat_last = data['final_post_weights']
        init_ff_weights = data['init_ff_connections']
        init_lat_weights = data['init_lat_connections']
        ff_init = data['init_ff_connections']
        lat_init = data['init_lat_connections']

        try:
            # retrieve some important sim params
            grid = simdata['grid']
            N_layer = grid[0] * grid[1]
            n = int(np.sqrt(N_layer))
            g_max = simdata['g_max']
            s_max = simdata['s_max']
            sigma_form_forward = simdata['sigma_form_forward']
            sigma_form_lateral = simdata['sigma_form_lateral']
            p_form_lateral = simdata['p_form_lateral']
            p_form_forward = simdata['p_form_forward']
            p_elim_dep = simdata['p_elim_dep']
            p_elim_pot = simdata['p_elim_pot']
            f_rew = simdata['f_rew']
        except:
            # use defaults
            grid = np.asarray([16, 16])
            N_layer = 256
            n = 32
            s_max = 16
            sigma_form_forward = 2.5
            sigma_form_lateral = 1
            p_form_lateral = 1
            p_form_forward = 0.16
            p_elim_dep = 0.0245
            p_elim_pot = 1.36 * np.e ** -4
            f_rew = 10 ** 4  # Hz
            g_max = .2

        total_target_neuron_mean_spike_rate = \
            post_spikes.shape[0] / float(simtime) * 1000. / N_layer

        last_conn, last_weight = list_to_post_pre(ff_last, lat_last,
                                                  s_max, N_layer)
        init_conn, init_weight = list_to_post_pre(ff_init, lat_init,
                                                  s_max, N_layer)

        #####     #####
        ## POST AREA ##
        #####     #####
        import scipy.io

        IntialConnectivity = scipy.io.loadmat(
            '2009_09_04.17_48_33 32Syn300s/InitialConnectivity.mat')
        Params = scipy.io.loadmat(
            '2009_09_04.17_48_33 32Syn300s/Params.mat')
        test_fan_in = fan_in(IntialConnectivity['ConnPostToPre'] - 1,
                             IntialConnectivity['WeightPostToPre'],
                             'conn',
                             'ff')
        other_fan_in = scipy.io.loadmat("fan_in.mat")['fan_in']

        assert np.all(test_fan_in == other_fan_in)
        mean_projection, means_and_std_devs, \
        means_for_plot, mean_centred_projection = centre_weights(
            test_fan_in, 16)

        test_odc = odc(test_fan_in)
        comparison_odc = scipy.io.loadmat("odc_init.mat")['OdcConnOnlyFin']
        assert np.all(test_odc == comparison_odc)

        # plt.plot(means_for_plot[:, 0], means_for_plot[:, 1])
        # plt.show()
        other_means_for_plot = scipy.io.loadmat("MeansForPlot")[
            'MeansForPlot']
        # plt.plot(other_means_for_plot[:, 0], other_means_for_plot[:, 1])
        # plt.show()

        # assert np.all(np.isclose(means_for_plot, other_means_for_plot))

        test_mean_std = np.mean(means_and_std_devs[:, 5])
        test_mean_AD = np.mean(means_and_std_devs[:, 4])
        test_stds = means_and_std_devs[:, 5]
        test_AD = means_and_std_devs[:, 4]
        MeansAndStuff = scipy.io.loadmat("means_and_std_devs.mat")

        other_mean_std = np.mean(MeansAndStuff['means_and_std_devs'][:, 5])
        other_mean_AD = np.mean(MeansAndStuff['means_and_std_devs'][:, 4])
        assert other_mean_std == test_mean_std
        assert other_mean_AD == test_mean_AD

        # harder test
        MeansAndStuff['means_and_std_devs'][:, [0, 1]] -= 1
        assert np.all(
            MeansAndStuff['means_and_std_devs'] == means_and_std_devs), \
            np.argwhere(
                MeansAndStuff['means_and_std_devs'] != means_and_std_devs)

        mean_centred_projection_matlab = \
            scipy.io.loadmat("mean_centred_projection")[
                'MeanCentredProjection']

        # np.argwhere(~np.isclose(mean_centred_projection, mean_centred_projection_matlab))
        assert np.all(np.isclose(mean_centred_projection,
                                 mean_centred_projection_matlab, 0.001,
                                 0.01))

        mean_projection_rad_con_init_rec = scipy.io.loadmat(
            'mean_proj_rad_con_init_rec.mat')['MeanProjRadConInitRec']

        fan_in_conn_init_rec = scipy.io.loadmat(
            'fan_in_conn_init_rec.mat')['FanInConnInitRec']

        mean_projection, means_and_std_devs, means_for_plot, mean_centred_projection = centre_weights(
            fan_in_conn_init_rec, 16)

        rad_test = radial_sample(mean_projection, 100)

        assert np.all(mean_projection_rad_con_init_rec == rad_test)

        #####     #####
        ## POST AREA ##
        #####     #####


        number_ff_incoming_connections = ff_last.shape[0]
        final_mean_number_ff_synapses = number_ff_incoming_connections / float(
            N_layer)

        initial_weight_mean = np.mean(ff_init[:, 2])

        final_weight_mean = np.mean(ff_last[:, 2])

        final_weight_proportion = final_weight_mean / initial_weight_mean

        # a

        init_fan_in = fan_in(init_conn, init_weight, 'conn', 'ff')

        mean_projection, means_and_std_devs, means_for_plot, mean_centred_projection = centre_weights(
            init_fan_in, 16)

        init_mean_std = np.mean(means_and_std_devs[:, 5])
        init_mean_AD = np.mean(means_and_std_devs[:, 4])
        init_stds = means_and_std_devs[:, 5]
        init_AD = means_and_std_devs[:, 4]

        init_conn_ff_odc = odc(init_fan_in)

        # b
        final_fan_in = fan_in(last_conn, last_weight, 'conn', 'ff')
        fin_mean_projection, fin_means_and_std_devs, fin_means_for_plot, fin_mean_centred_projection = centre_weights(
            final_fan_in, 16)
        fin_mean_std_conn = np.mean(fin_means_and_std_devs[:, 5])
        fin_mean_AD_conn = np.mean(fin_means_and_std_devs[:, 4])
        fin_stds_conn = fin_means_and_std_devs[:, 5]
        fin_AD_conn = fin_means_and_std_devs[:, 4]

        fin_conn_ff_odc = odc(final_fan_in)

        # c

        init_ff_connections = []
        ff_s = np.zeros(N_layer, dtype=np.uint)
        lat_s = np.zeros(N_layer, dtype=np.uint)
        existing_pre_ff = []
        generated_ff_conn = []
        generated_lat_conn = []

        generate_initial_connectivity(
            ff_s, generated_ff_conn,
            sigma_form_forward, p_form_forward,
            "\nGenerating initial feedforward connectivity...",
            N_layer=N_layer, n=n, s_max=s_max, g_max=g_max)

        generate_initial_connectivity(
            lat_s, generated_lat_conn,
            sigma_form_lateral, p_form_lateral,
            "\nGenerating initial lateral connectivity...",
            N_layer=N_layer, n=n, s_max=s_max, g_max=g_max)

        gen_init_conn, gen_init_weight = \
            list_to_post_pre(np.asarray(generated_ff_conn),
                             np.asarray(generated_lat_conn), s_max,
                             N_layer)

        gen_fan_in = fan_in(gen_init_conn, gen_init_weight, 'conn', 'ff')

        fin_mean_projection_shuf, fin_means_and_std_devs_shuf, \
        fin_means_for_plot_shuf, fin_mean_centred_projection_shuf = \
            centre_weights(gen_fan_in, 16)

        fin_mean_std_conn_shuf = np.mean(fin_means_and_std_devs_shuf[:, 5])
        fin_mean_AD_conn_shuf = np.mean(fin_means_and_std_devs_shuf[:, 4])
        fin_stds_conn_shuf = fin_means_and_std_devs_shuf[:, 5]
        fin_AD_conn_shuf = fin_means_and_std_devs_shuf[:, 4]

        wsr_sigma_fin_conn_fin_conn_shuffle = stats.wilcoxon(
            fin_stds_conn.ravel(), fin_stds_conn_shuf.ravel())
        wsr_AD_fin_conn_fin_conn_shuffle = stats.wilcoxon(
            fin_AD_conn.ravel(),
            fin_AD_conn_shuf.ravel())
        # d
        final_fan_in_weight = fan_in(last_conn, last_weight, 'weight',
                                     'ff')
        # final_fan_in_weight = conn_matrix_to_fan_in(ff_last, mode='weight')
        fin_mean_projection_weight, fin_means_and_std_devs_weight, fin_means_for_plot_weight, fin_mean_centred_projection_weight = centre_weights(
            final_fan_in_weight, 16)
        fin_mean_std_weight = np.mean(fin_means_and_std_devs_weight[:, 5])
        fin_mean_AD_weight = np.mean(fin_means_and_std_devs_weight[:, 4])
        fin_stds_weight = fin_means_and_std_devs_weight[:, 5]
        fin_AD_weight = fin_means_and_std_devs_weight[:, 4]

        fin_weight_ff_odc = odc(final_fan_in_weight)

        # e

        weight_copy = weight_shuffle(last_conn, last_weight, 'ff')
        shuf_weights = fan_in(last_conn, weight_copy, 'weight', 'ff')

        fin_mean_projection_weight_shuf, fin_means_and_std_devs_weight_shuf, fin_means_for_plot_weight_shuf, fin_mean_centred_projection_weight_shuf = centre_weights(
            shuf_weights, 16)
        fin_mean_std_weight_shuf = np.mean(
            fin_means_and_std_devs_weight_shuf[:, 5])
        fin_mean_AD_weight_shuf = np.mean(
            fin_means_and_std_devs_weight_shuf[:, 4])
        fin_stds_weight_shuf = fin_means_and_std_devs_weight_shuf[:, 5]
        fin_AD_weight_shuf = fin_means_and_std_devs_weight_shuf[:, 4]

        wsr_sigma_fin_weight_fin_weight_shuffle = stats.wilcoxon(
            fin_stds_weight.ravel(), fin_stds_weight_shuf.ravel())
        wsr_AD_fin_weight_fin_weight_shuffle = stats.wilcoxon(
            fin_AD_weight.ravel(), fin_AD_weight_shuf.ravel())

        print
        pp(simdata)
        print
        print "%-60s" % "Target neuron spike rate", total_target_neuron_mean_spike_rate, "Hz"
        print "%-60s" % "Final mean number of feedforward synapses", final_mean_number_ff_synapses
        print "%-60s" % "Weight as proportion of max", final_weight_proportion
        print "%-60s" % "Mean sigma aff init", init_mean_std
        print "%-60s" % "Mean sigma aff fin conn shuffle", fin_mean_std_conn_shuf
        print "%-60s" % "Mean sigma aff fin conn", fin_mean_std_conn
        print "%-60s" % "p(WSR sigma aff fin conn vs sigma aff fin conn shuffle)", wsr_sigma_fin_conn_fin_conn_shuffle.pvalue
        print "%-60s" % "Mean sigma aff fin weight shuffle", fin_mean_std_weight_shuf
        print "%-60s" % "Mean sigma aff fin weight", fin_mean_std_weight
        print "%-60s" % "p(WSR sigma aff fin weight vs sigma aff fin weight shuffle)", wsr_sigma_fin_weight_fin_weight_shuffle.pvalue
        print "%-60s" % "Mean AD init", init_mean_AD
        print "%-60s" % "Mean AD fin conn shuffle", fin_mean_AD_conn_shuf
        print "%-60s" % "Mean AD fin conn", fin_mean_AD_conn
        print "%-60s" % "p(WSR AD fin conn vs AD fin conn shuffle)", wsr_AD_fin_conn_fin_conn_shuffle.pvalue
        print "%-60s" % "Mean AD fin weight shuffle", fin_mean_AD_weight_shuf
        print "%-60s" % "Mean AD fin weight", fin_mean_AD_weight
        print "%-60s" % "p(WSR AD fin weight vs AD fin weight shuffle)", wsr_AD_fin_weight_fin_weight_shuffle.pvalue

        # LAT connection bar chart

        init_fan_in_rec = fan_in(init_conn, init_weight, 'conn', 'rec')

        mean_projection_rec, means_and_std_devs_rec, \
        means_for_plot_rec, mean_centred_projection_rec = centre_weights(
            init_fan_in_rec, 16)

        init_fan_in_rec_rad = radial_sample(mean_projection_rec, 100)

        final_fan_in_rec = fan_in(last_conn, last_weight, 'weight',
                                  'rec')

        final_mean_projection_rec, final_means_and_std_devs_rec, \
        final_means_for_plot_rec, final_mean_centred_projection_rec = centre_weights(
            final_fan_in_rec, 16)

        final_fan_in_rec_rad = \
            radial_sample(final_mean_projection_rec, 100)

        final_fan_in_rec_conn = fan_in(last_conn, last_weight, 'conn',
                                       'rec')

        final_mean_projection_rec_conn, final_means_and_std_devs_rec_conn, \
        final_means_for_plot_rec_conn, final_mean_centred_projection_rec_conn = centre_weights(
            final_fan_in_rec_conn, 16)

        final_fan_in_rec_rad_conn = \
            radial_sample(final_mean_projection_rec_conn, 100)

        ## FF connection bar chart

        init_fan_in_ff = fan_in(init_conn, init_weight, 'conn', 'ff')

        mean_projection_ff, means_and_std_devs_ff, \
        means_for_plot_ff, mean_centred_projection_ff = centre_weights(
            init_fan_in_ff, 16)

        init_fan_in_ff_rad = radial_sample(mean_projection_ff, 100)

        final_fan_in_ff = fan_in(last_conn, last_weight, 'weight',
                                 'ff')

        final_mean_projection_ff, final_means_and_std_devs_ff, \
        final_means_for_plot_ff, final_mean_centred_projection_ff = centre_weights(
            final_fan_in_ff, 16)

        final_fan_in_ff_rad = \
            radial_sample(final_mean_projection_ff, 100)

        final_fan_in_ff_conn = fan_in(last_conn, last_weight, 'conn',
                                      'ff')

        final_mean_projection_ff_conn, final_means_and_std_devs_ff_conn, \
        final_means_for_plot_ff_conn, final_mean_centred_projection_ff_conn = centre_weights(
            final_fan_in_ff_conn, 16)

        final_fan_in_ff_rad_conn = \
            radial_sample(final_mean_projection_ff_conn, 100)

        # Time stuff

        end_time = plt.datetime.datetime.now()
        suffix = end_time.strftime("_%H%M%S_%d%m%Y")

        elapsed_time = end_time - start_time

        print "Total time elapsed -- " + str(elapsed_time)

        if args.filename:
            filename = args.filename
        else:
            filename = "analysis_" + str(suffix)

        np.savez(filename, recording_archive_name=file,
                 target_neurom_mean_spike_rate=total_target_neuron_mean_spike_rate,
                 final_mean_number_ff_synapses=final_mean_number_ff_synapses,
                 final_weight_proportion=final_weight_proportion,
                 init_ff_weights=init_ff_weights,
                 init_lat_connections=init_lat_weights,
                 final_pre_weights=ff_last,
                 final_post_weights=lat_last,
                 # a
                 init_mean_std=init_mean_std, init_stds=init_stds,
                 init_mean_AD=init_mean_AD,
                 init_AD=init_AD,
                 # b
                 fin_mean_std_conn=fin_mean_std_conn,
                 fin_stds_conn=fin_stds_conn,
                 fin_mean_AD_conn=fin_mean_AD_conn,
                 fin_AD_conn=fin_AD_conn,
                 # c
                 generated_ff_conn=generated_ff_conn,
                 fin_mean_std_conn_shuf=fin_mean_std_conn_shuf,
                 fin_stds_conn_shuf=fin_stds_conn_shuf,
                 fin_mean_AD_conn_shuf=fin_mean_AD_conn_shuf,
                 fin_AD_conn_shuf=fin_AD_conn_shuf,
                 wsr_sigma_fin_conn_fin_conn_shuffle=wsr_sigma_fin_conn_fin_conn_shuffle,
                 wsr_AD_fin_conn_fin_conn_shuffle=wsr_AD_fin_conn_fin_conn_shuffle,
                 # d
                 fin_mean_std_weight=fin_mean_std_weight,
                 fin_stds_weight=fin_stds_weight,
                 fin_mean_AD_weight=fin_mean_AD_weight,
                 fin_AD_weight=fin_AD_weight,
                 # e
                 shuf_weights=shuf_weights,
                 fin_mean_std_weight_shuf=fin_mean_std_weight_shuf,
                 fin_stds_weight_shuf=fin_stds_weight_shuf,
                 fin_mean_AD_weight_shuf=fin_mean_AD_weight_shuf,
                 fin_AD_weight_shuf=fin_AD_weight_shuf,
                 wsr_sigma_fin_weight_fin_weight_shuffle=wsr_sigma_fin_weight_fin_weight_shuffle,
                 wsr_AD_fin_weight_fin_weight_shuffle=wsr_AD_fin_weight_fin_weight_shuffle,
                 total_time=elapsed_time,
                 # radial sampling -- lateral
                 init_fan_in_rec_rad=init_fan_in_rec_rad,
                 final_fan_in_rec_rad=final_fan_in_rec_rad,
                 final_fan_in_rec_rad_conn=final_fan_in_rec_rad_conn,
                 # radial sampling -- feedforward
                 init_fan_in_ff_rad=init_fan_in_ff_rad,
                 final_fan_in_ff_rad=final_fan_in_ff_rad,
                 final_fan_in_ff_rad_conn=final_fan_in_ff_rad_conn,
                 # occularity
                 fin_conn_ff_odc=fin_conn_ff_odc,
                 fin_weight_ff_odc=fin_weight_ff_odc,
                 # map sequence
                 fin_means_for_plot_weight=fin_means_for_plot_weight,
                 init_means_for_plot=means_for_plot
                 )

        if args.plot:
            fig_conn, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8),
                                                sharey=True)

            ff_conn_ax = ax1.matshow(fin_conn_ff_odc, vmin=0, vmax=1,
                                     cmap='viridis')
            lat_conn_ax = ax2.matshow(fin_weight_ff_odc, vmin=0, vmax=1,
                                      cmap='viridis')

            ax1.set_title("{}".format(np.mean(fin_conn_ff_odc)))
            ax2.set_title("{}".format(np.mean(fin_weight_ff_odc)))

            cbar_ax = fig_conn.add_axes([.91, 0.155, 0.025, 0.72])
            cbar = fig_conn.colorbar(lat_conn_ax, cax=cbar_ax)
            cbar.set_label("Occularity measure", fontsize=12)
            plt.show()

            plt.figure()
            plt.subplot(1, 3, 1)
            plt.suptitle(
                "Distance between input and target neurons for lateral connections")
            plt.bar(range(8), init_fan_in_rec_rad)
            plt.ylim([0, 3])
            plt.xticks(range(8))
            plt.ylabel("Weight density (normalised)")
            plt.subplot(1, 3, 2)
            plt.bar(range(8), final_fan_in_rec_rad)
            plt.subplot(1, 3, 3)
            plt.bar(range(8), final_fan_in_rec_rad_conn)
            plt.show()

            plt.figure()
            plt.subplot(1, 3, 1)
            plt.suptitle(
                "Distance between input and target neurons for feedforward connections")
            plt.bar(range(8), init_fan_in_ff_rad)
            plt.ylim([0, .5])
            plt.xticks(range(8))
            plt.ylabel("Weight density (normalised)")
            plt.subplot(1, 3, 2)
            plt.bar(range(8), final_fan_in_ff_rad)
            plt.subplot(1, 3, 3)
            plt.bar(range(8), final_fan_in_ff_rad_conn)
            plt.ylim([0, .5])
            plt.show()

            plt.figure()
            plt.subplot(1, 2, 1)
            plt.suptitle("Map formation sequence")
            plt.title("Initial map")
            plt.plot(means_for_plot[:, 0], means_for_plot[:, 1])
            plt.subplot(1, 2, 2)
            plt.title("Final map")
            plt.plot(fin_means_for_plot_weight[:, 0],
                     fin_means_for_plot_weight[:, 1])
            # plt.ylabel("Weight density (normalised)")

            plt.show()

        if args.snapshots:

            all_ff_connections = data['ff_connections']
            all_lat_connections = data['lat_connections']
            if data:
                data.close()
            number_of_recordings = all_ff_connections.shape[0]
            all_mean_sigmas = np.ones(number_of_recordings) * np.nan
            all_mean_ADs = np.ones(number_of_recordings) * np.nan
            for index in range(number_of_recordings):
                conn, weight = \
                    list_to_post_pre(all_ff_connections[index],
                                     all_lat_connections[index], 16,
                                     N_layer)

                current_fan_in = fan_in(conn, weight, 'weight', 'ff')
                mean_projection, means_and_std_devs, means_for_plot, mean_centred_projection = centre_weights(
                    current_fan_in, 16)

                all_mean_sigmas[index] = np.mean(means_and_std_devs[:, 5])
                all_mean_ADs[index] = np.mean(means_and_std_devs[:, 4])

                # mean_std, stds, mean_AD, AD, variances = sigma_and_ad(
                #     all_ff_connections[index, :, :],
                #     unitary_weights=False,
                #     resolution=args.resolution)
                # all_mean_sigmas[index] = mean_std
                # all_mean_ADs[index] = mean_AD
            np.savez("last_std_ad_evo", recording_archive_name=file,
                     all_mean_sigmas=all_mean_sigmas,
                     all_mean_ads=all_mean_ADs)
            if args.plot:
                plt.plot(all_mean_sigmas)
                plt.ylim([0, 1.1 * np.max(all_mean_sigmas)])
                plt.show()
                plt.plot(all_mean_ADs)
                plt.ylim([0, 1.1 * np.max(all_mean_ADs)])
                plt.show()

    except IOError as e:
        print "IOError:", e
    except MemoryError:
        print "Out of memory. Did you use HDF5 slices to read in data?", e
    finally:
        data.close()

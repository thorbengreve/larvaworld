import heapq
import itertools

import matplotlib.patches as mpatches
import pandas as pd
import seaborn as sns
from matplotlib import cm, transforms, ticker, patches
from matplotlib.patches import Wedge
from matplotlib.ticker import ScalarFormatter
from mpl_toolkits.mplot3d import Axes3D
from scipy import signal
from scipy import stats
from scipy.interpolate import griddata
from scipy.signal import butter, sosfiltfilt
from sklearn.linear_model import LinearRegression
import powerlaw as pow

from PIL import Image

from lib.anal.fitting import *
from lib.aux.functions import weib, flatten_list, N_colors
from lib.anal.combining import combine_images, combine_pdfs

from lib.stor.paths import DebFolder
from lib.conf.par_db import par_db

'''
Generic plot function. Uses the next two functions internally'''

plt_conf = {'axes.labelsize': 20,
            'axes.titlesize': 25,
            'figure.titlesize': 30,
            'xtick.labelsize': 20,
            'ytick.labelsize': 20,
            'legend.fontsize': 15,
            'legend.title_fontsize': 15}
plt.rcParams.update(plt_conf)
suf = 'pdf'


# suf = 'png'


def mean_confidence_interval(data, confidence=0.95):
    n = len(data)
    m = np.nanmean(data, axis=0)
    se = stats.sem(data, axis=0, nan_policy='omit')
    h = se * stats.t.ppf((1 + confidence) / 2., n - 1)
    return m, m - h, m + h


def plot_mean_and_range(x, mean, lb, ub, axis, color_mean=None, color_shading=None, label=None):
    # plot the shaded range of e.g. the confidence intervals
    axis.fill_between(x, ub, lb, color=color_shading, alpha=.2)
    # plot the mean on top
    if label is not None:
        axis.plot(x, mean, color_mean, label=label)
    else:
        axis.plot(x, mean, color_mean)

    # pass


# def plot_dataset_for_each(agent_ids, **kwargs):
#     for agent_id in agent_ids:
#         plot_dataset(agent_ids=[agent_id], **kwargs)


def plot_dataset(save_to, save_as=None, mode='time', subplot_structure=[1, 1],
                 figsize=(15, 10), ticksize=15, labelsize=15, titlesize=25, figtitlesize=30, legendsize=15,
                 legendtitlesize=20, draw_y0=False, log=False,
                 title=None, log_yscale=False, xlim=None, ylim=None, xlabel=None, ylabel=None,
                 sharex=False, sharey=False, **kwargs):
    plot_config = {'axes.labelsize': labelsize,
                   'axes.titlesize': titlesize,
                   'figure.titlesize': figtitlesize,
                   'xtick.labelsize': ticksize,
                   'ytick.labelsize': ticksize,
                   'legend.fontsize': legendsize,
                   'legend.title_fontsize': legendtitlesize}
    plt.rcParams.update(plot_config)
    fig, axs = plt.subplots(subplot_structure[0], subplot_structure[1], sharex=sharex, sharey=sharey, figsize=figsize)

    N = subplot_structure[0] * subplot_structure[1]
    if N > 1:
        axs = axs.ravel()
    else:
        axs = [axs]

    if mode == 'time':
        fig, filename = time_plot(fig, axs, Nsubplots=N, **kwargs)
    elif mode == 'parsed_time':
        fig, filename = parsed_time_plot(fig, axs, Nsubplots=N, **kwargs)
    elif mode == 'hist':
        fig, filename = hist_plot(fig, axs, Nsubplots=N, log=log, **kwargs)
    elif mode == 'spect':
        fig, filename = spectogram(fig, axs, Nsubplots=N, **kwargs)

    for i in range(N):
        ax = axs[i]
        if title:
            if isinstance(title, list) and len(title) == N:
                ax.set_title(title[i])
            else:
                ax.set_title(title)
        if xlabel:
            if isinstance(xlabel, list) and len(xlabel) == N:
                ax.set_xlabel(xlabel[i])
            else:
                ax.set_xlabel(xlabel)
        if ylabel:
            if isinstance(ylabel, list) and len(ylabel) == N:
                ax.set_ylabel(ylabel[i])
            else:
                ax.set_ylabel(ylabel)
        if xlim:
            if isinstance(xlim, list):
                if isinstance(xlim[i], list):
                    ax.set_xlim(xlim[i])
                else:
                    ax.set_xlim(xlim)
            else:
                ax.set_xlim(xlim)
        if ylim:
            if isinstance(ylim, list):
                if isinstance(ylim[0], list):
                    ax.set_ylim(ylim[i])
                else:
                    ax.set_ylim(ylim)
            else:
                ax.set_ylim(ylim)
        if draw_y0 == True:
            plt.axhline(0, color='green', alpha=0.5, linestyle='dashed', linewidth=1)
        if log:
            plt.gca().set_xscale("log")
        if log_yscale:
            plt.yscale('log')
        plt.tight_layout()

    if save_as:
        filename = save_as
    filepath = os.path.join(save_to, filename)
    save_plot(fig, filepath, filename)


def parsed_time_plot(fig, axs, data, agent_ids, parameters, dt=None, Nsubplots=1,
                     plot_mean=False, plot_quantiles=False, plot_CI=False,
                     absolute=False, cumulative=False, parsing_flags=None, condition_flags=None,
                     center_flag=None, radius_in_sec=None, chunk=None, normalize_to_period=False, **kwargs):
    if len(parameters) != Nsubplots:
        raise ValueError('Number of subplots does not match number of parameters')
    # print(axs, len(axs), axs[0])
    # print(parameters)

    all_agents = [data.xs(agent_id, level='AgentID', drop_level=True) for agent_id in agent_ids]
    if parsing_flags is not None:
        all_flag_starts = [ag[ag[parsing_flags[0]] == True].index.values.astype(int) for ag in all_agents]
        all_flag_stops = [ag[ag[parsing_flags[1]] == True].index.values.astype(int) for ag in all_agents]
    elif center_flag is not None and radius_in_sec is not None:
        radius_in_ticks = np.ceil(radius_in_sec / dt)
        all_flags = [ag[ag[center_flag] == True].index.values for ag in all_agents]
        all_flag_starts = [(flags - radius_in_ticks).astype(int) for flags in all_flags]
        all_flag_stops = [(flags + radius_in_ticks).astype(int) for flags in all_flags]
    elif chunk is not None:
        all_flag_starts = [ag[ag[nam.start(chunk)] == True].index.values.astype(int) for ag in all_agents]
        all_flag_stops = [ag[ag[nam.stop(chunk)] == True].index.values.astype(int) for ag in all_agents]

    for i, param in enumerate(parameters):
        # print(i, param)
        timeseries = []
        for agent_id, flag_starts, flag_stops in zip(agent_ids, all_flag_starts, all_flag_stops):
            for start, stop in zip(flag_starts, flag_stops):
                if condition_flags is not None:
                    if condition_flags[0] is not None:
                        v = data.loc[(start, agent_id), condition_flags[0][0]]
                        if condition_flags[0][1] == 'higher' and not v >= condition_flags[0][2]:
                            continue
                        elif condition_flags[0][1] == 'lower' and not v <= condition_flags[0][2]:
                            continue
                        elif condition_flags[0][1] == 'equal' and not v == condition_flags[0][2]:
                            continue
                    if condition_flags[1] is not None:
                        v = data.loc[(stop, agent_id), condition_flags[1][0]]
                        if condition_flags[1][1] == 'higher' and not v >= condition_flags[1][2]:
                            continue
                        elif condition_flags[1][1] == 'lower' and not v <= condition_flags[1][2]:
                            continue
                        elif condition_flags[1][1] == 'equal' and not v == condition_flags[1][2]:
                            continue
                try:
                    timeserie = data.loc[(slice(start, stop), agent_id), param].values
                    if cumulative:
                        timeserie = timeserie.cumsum()

                    timeseries.append(timeserie)
                except:
                    pass
        durations = [len(i) for i in timeseries]
        if normalize_to_period:
            Npoints = 32
            timeseries_array = [
                np.interp(x=np.linspace(0, 2 * np.pi, Npoints), xp=np.linspace(0, 2 * np.pi, dur), fp=ts, left=0,
                          right=0) for dur, ts in
                zip(durations, timeseries)]
        else:
            max_duration = np.max(durations)
            timeseries_array = np.empty([len(timeseries), max_duration])
            for i, j in enumerate(timeseries):
                timeseries_array[i][0:len(j)] = j
        if absolute:
            timeseries_array = np.abs(timeseries_array)

        # print(i,param)
        ax = axs[i]
        ax.set_title(f'{param} temporal parsing')
        ax.set_ylabel(param)
        ax.set_xlabel('time $(sec)$')

        if plot_CI:
            ts_m, ts_l, ts_h = mean_confidence_interval(timeseries_array, confidence=0.95)
            # print(ts_m, ts_l, ts_h)
            plot_mean_and_range(x=np.arange(len(ts_m)), mean=ts_m, lb=ts_l, ub=ts_h, axis=ax, color_mean='b',
                                color_shading='grey')
        elif plot_mean:
            ax.plot(np.nanmean(timeseries_array, axis=0), 'r', linewidth=3, linestyle="--")
        elif plot_quantiles is not None:
            if plot_quantiles == 3:
                ts_m, ts_l, ts_h = np.nanquantile(timeseries_array, q=0.5, axis=0), \
                                   np.nanquantile(timeseries_array, q=0.25, axis=0), \
                                   np.nanquantile(timeseries_array, q=0.75, axis=0)
                # print(ts_m, ts_l, ts_h)
                plot_mean_and_range(x=np.arange(len(ts_m)), mean=ts_m, lb=ts_l, ub=ts_h, axis=ax, color_mean='black',
                                    color_shading='grey', label=r'$\dot{\theta}_{or}$')
                ax.legend(loc=1, fontsize=12)
                # ax.plot(np.nanquantile(timeseries_array, q=0.5, axis=0), 'r', linewidth=3, linestyle="-")
                # ax.plot(np.nanquantile(timeseries_array, q=0.25, axis=0), 'b', linewidth=2, linestyle="--")
                # ax.plot(np.nanquantile(timeseries_array, q=0.75, axis=0), 'b', linewidth=2, linestyle="--")
            elif plot_quantiles == 7:
                ax.plot(np.nanquantile(timeseries_array, q=0.5, axis=0), 'r', linewidth=2, linestyle="-")
                ax.plot(np.nanquantile(timeseries_array, q=0.35, axis=0), 'b', linewidth=2, linestyle="--")
                ax.plot(np.nanquantile(timeseries_array, q=0.65, axis=0), 'b', linewidth=2, linestyle="--")
                ax.plot(np.nanquantile(timeseries_array, q=0.2, axis=0), 'g', linewidth=2, linestyle="--")
                ax.plot(np.nanquantile(timeseries_array, q=0.8, axis=0), 'g', linewidth=2, linestyle="--")
                ax.plot(np.nanquantile(timeseries_array, q=0.05, axis=0), 'c', linewidth=2, linestyle="--")
                ax.plot(np.nanquantile(timeseries_array, q=0.95, axis=0), 'c', linewidth=2, linestyle="--")
            else:
                raise ValueError('Currently only 3 and 7 quantiles are supported')
        else:
            [ax.plot(t, color='grey', alpha=0.3) for t in timeseries_array]

    # print(ticks)
    if parsing_flags is not None:
        ticks = np.arange(max_duration)
        ax.set_xticks(ticks=ticks)
        ax.set_xticklabels(labels=ticks * dt)
    elif center_flag is not None and radius_in_sec is not None:
        ticks = np.arange(max_duration)
        ax.set_xticks(ticks=ticks)
        ax.set_xticklabels(labels=(ticks - (max_duration - 1) / 2) * dt)
    elif normalize_to_period:
        Nticks = 5
        ticks = np.linspace(0, Npoints - 1, Nticks)
        # ax.locator_params(axis='x', nbins=Nticks)
        ax.set_xticks(ticks=ticks)
        ax.set_xticklabels(labels=[r'$0$', r'$\frac{\pi}{2}$', r'$\pi$', r'$\frac{3\pi}{2}$', r'$2\pi$'])
        ax.set_xlim([0, Npoints - 1])

    # plt.legend(loc='upper right')
    filename = f'{parameters}_parsed.jpg'
    return fig, filename


def time_plot(fig, axs, data, agent_ids, parameters, dt=None, Nsubplots=1,
              plot_mean=False, plot_quantiles=None, plot_CI=False, secondary_ylabel=None,
              marker_params=None, background_flags=None, background_for_chunks=None, legend_labels=None,
              background_vertical_boundaries=True, show_legend=True, show_par_legend=True,
              time_in_sec=True, time_in_min=False, time_in_hours=False, **kwargs):
    my_data = data.copy()
    # TODO Use 'absolute' parameter
    if dt:
        if time_in_sec:
            l = 'time $(sec)$'
            my_data.index.set_levels(my_data.index.levels[0] * dt, level=0, inplace=True)
        elif time_in_min:
            l = 'time $(min)$'
            my_data.index.set_levels(my_data.index.levels[0] * dt / 60, level=0, inplace=True)
        elif time_in_hours:
            l = 'time $(hours)$'
            my_data.index.set_levels(my_data.index.levels[0] * dt / 3600, level=0, inplace=True)
    else:
        l = 'time $(ticks)$'
    # axs.set_xlabel(l)
    # print(my_data.index.values)
    # print(my_data.index.levels[0].min())
    trange = my_data.index.unique(level='Step')
    plt.xlim([np.min(my_data.index.levels[0].values), np.max(my_data.index.levels[0].values)])
    plt.xlabel(l)
    if len(parameters) == 1:
        param = parameters[0]
        if plot_CI:
            ts_m, ts_l, ts_h = mean_confidence_interval(my_data[param].values, confidence=0.95)
            plot_mean_and_range(x=trange, mean=ts_m, lb=ts_l, ub=ts_h, axis=axs[0], color_mean='b',
                                color_shading='grey')
        elif plot_mean == True:
            mean_series = my_data[param].groupby(level='Step').mean()
            plt.plot(mean_series, 'r', linewidth=3, linestyle="--")
        elif plot_quantiles is not None:
            ts_m = my_data[param].groupby(level='Step').median()
            if plot_quantiles == 3:
                ts_l = my_data[param].groupby(level='Step').quantile(0.25)
                ts_h = my_data[param].groupby(level='Step').quantile(0.75)
                plot_mean_and_range(x=trange, mean=ts_m, lb=ts_l, ub=ts_h, axis=axs[0], color_mean='b',
                                    color_shading='grey')
                # plt.plot(aa, 'b', linewidth=2, linestyle="--")
                # plt.plot(bb, 'b', linewidth=2, linestyle="--")
            elif plot_quantiles == 7:
                plt.plot(ts_m, 'r', linewidth=3, linestyle="-")
                aa = my_data[param].groupby(level='Step').quantile(0.35)
                bb = my_data[param].groupby(level='Step').quantile(0.65)
                cc = my_data[param].groupby(level='Step').quantile(0.2)
                ddd = my_data[param].groupby(level='Step').quantile(0.8)
                ee = my_data[param].groupby(level='Step').quantile(0.05)
                ff = my_data[param].groupby(level='Step').quantile(0.95)

                plt.plot(aa, 'b', linewidth=2, linestyle="--")
                plt.plot(bb, 'b', linewidth=2, linestyle="--")
                plt.plot(cc, 'g', linewidth=2, linestyle="--")
                plt.plot(ddd, 'g', linewidth=2, linestyle="--")
                plt.plot(ee, 'c', linewidth=2, linestyle="--")
                plt.plot(ff, 'c', linewidth=2, linestyle="--")
        else:
            for i, agent_id in enumerate(agent_ids):
                agent_data = my_data.xs(agent_id, level='AgentID', drop_level=True)
                if len(agent_ids) > 5:
                    plt.plot(agent_data[param], color='grey', alpha=0.5)
                else:
                    plt.plot(agent_data[param], color='blue')
        plt.title(f'{param} of multiple larvae')
        plt.ylabel(param)
        filename = f'{param}_of_multiple_larvae.jpg'
    elif len(parameters) == 2 and len(agent_ids) == 1:
        agent_id = agent_ids[0]
        param1, param2 = parameters
        d1 = my_data[param1].xs(agent_id, level='AgentID', drop_level=True)
        d2 = my_data[param2].xs(agent_id, level='AgentID', drop_level=True)

        # plt.legend(loc= 'upper left')
        if secondary_ylabel is None:
            secondary_y_label = param2

        handles, labels = [], []
        if show_par_legend:
            ax1 = d1.plot(label=param1)
            ax1.set_ylabel(param1)
            ax2 = d2.plot(secondary_y=True, label=secondary_ylabel)
            ax2.set_ylabel(secondary_ylabel)
            for ax in fig.axes:
                for h, l in zip(*ax.get_legend_handles_labels()):
                    handles.append(h)
                    labels.append(l)

            plt.legend(handles, labels, loc='upper right')
        else:
            ax1 = d1.plot()
            ax1.set_ylabel(param1)
            ax2 = d2.plot(secondary_y=True)
            ax2.set_ylabel(secondary_ylabel)
        # plt.legend((a, b),
        #            (param1, param2), loc='upper right')
        # plt.title(f'{param1} vs {param2} for {agent_id} ')
        try:
            axs.set_xlabel(l)
        except:
            pass
        # TODO This causes problems with more than one param. or maybe not
        filename = f'{param1}_vs_{param2}_for_{agent_id}.jpg'
        # filename = f'{parameters}_of_{agent_id}.jpg'
        # print(filename)
    elif len(parameters) > 2 and len(agent_ids) == 1:
        agent_id = agent_ids[0]
        viridis = cm.get_cmap('viridis', len(parameters))
        colors = viridis(np.linspace(0, 1, len(parameters)))
        # colors = cm.rainbow(np.linspace(0, 1, len(parameters)))
        for parameter, c in zip(parameters, colors):
            # print(parameter)
            d = my_data[parameter].xs(agent_id, level='AgentID', drop_level=True)
            plt.plot(d, label=parameter, color=c)
        plt.title(f'{parameters} of {agent_id} ')
        plt.ylabel(parameters)
        if show_legend:
            plt.legend()
        # TODO This causes problems with more than one param. or maybe not
        filename = f'parameters_of_{agent_id}.jpg'
        # filename = f'{parameters}_of_{agent_id}.jpg'
        # print(filename)
    else:
        raise ('Can not plot more than 1 parametres for multiple agents')
    if len(agent_ids) == 1:
        agent_data = my_data.xs(agent_ids[0], level='AgentID', drop_level=True)
        if background_flags:
            for i, flag in enumerate(background_flags):
                # print(flag,i)
                flag_data = agent_data[flag].dropna()
                flag_indexes = flag_data.index.values
                flag_starts = [i for i in flag_indexes if i - dt not in flag_indexes]
                flag_stops = [i for i in flag_indexes if i + dt not in flag_indexes]
                for start, end in zip(flag_starts, flag_stops):
                    plt.axvspan(start, end, facecolor=f'{0.2 * (i + 1)}', alpha=0.5)
        if background_for_chunks is not None:
            cmap = cm.get_cmap('Pastel2')
            num_chunks = len(background_for_chunks)
            colors = [cmap(i) for i in np.arange(num_chunks)]
            colors = ['white', 'grey']
            if show_legend:
                if legend_labels is None:
                    patches = [mpatches.Patch(color=color, label=name) for name, color in
                               zip(background_for_chunks, colors)]
                else:
                    patches = [mpatches.Patch(color=color, label=name) for name, color in
                               zip(legend_labels, colors)]
                plt.legend(handles=patches, loc='upper right', prop={'size': 15})
            for i, (chunk, color) in enumerate(zip(background_for_chunks, colors)):
                start_flag = f'{chunk}_start'
                stop_flag = f'{chunk}_stop'
                start_indexes = agent_data.index[agent_data[start_flag] == True]
                stop_indexes = agent_data.index[agent_data[stop_flag] == True]
                for start, stop in zip(start_indexes, stop_indexes):
                    # print(start, stop, stop-start)
                    plt.axvspan(start, stop, color=color, alpha=1.0)
                    if background_vertical_boundaries:
                        plt.axvline(start, color=f'{0.4 * (i + 1)}', alpha=0.6, linestyle='dashed', linewidth=1)
                        plt.axvline(stop, color=f'{0.4 * (i + 1)}', alpha=0.6, linestyle='dashed', linewidth=1)
        if marker_params:
            for i, par in enumerate(marker_params):
                dd = agent_data[par].values
                # print(dd==True)
                flagged_d = agent_data[parameters[0]].loc[dd == True]
                # print(flagged_d)
                if i == 0:
                    plt.plot(flagged_d, linestyle='None', lw=10, color='green', marker='v')
                elif i == 1:
                    plt.plot(flagged_d, linestyle='None', lw=10, color='red', marker='^')
                else:
                    print('Currently only two marker parameters are supported')
                    pass

    return fig, filename


def hist_plot(fig, axs, data, agent_ids, parameters, Nsubplots=1,
              density=False, log=False, num_bins=50, cumulative=False, bins=None,
              absolute=False, show_median=False, flag_intervals=False, fit_curve=False, condition_flags=None,
              show_legend=True, **kwargs):
    num_agents = len(agent_ids)
    if len(parameters) == 1:
        param = parameters[0]
        if flag_intervals:
            for agent_id in agent_ids:
                agent_data = data.xs(agent_id, level='AgentID', drop_level=True)
                t = agent_data[agent_data[param] == True]
                ticks = t.index.values
                d = np.diff(ticks)
        elif condition_flags is not None:
            if len(condition_flags) != 1:
                raise ValueError('Not implemented multiple selection flags.')
            else:
                flag = condition_flags[0][0]
                mode = condition_flags[0][1]
                print(f'Selecting data based on parameter {flag} being {mode}')
                if mode == 'nan':
                    temp_d = data[data[flag].isna()]
                elif mode == 'non_nan':
                    temp_d = data[data[flag].notna()]
                d = temp_d.loc[(slice(None), agent_ids), param].dropna().values
            # pass
        else:
            d = data.loc[(slice(None), agent_ids), param].dropna().values
        # d = data[param].xs(agent_ids, level='AgentID', drop_level=True).dropna().values
        if absolute:
            d = np.abs(d)
        if log:
            my_bins = np.logspace(np.min(np.log10(d)), np.max(np.log10(d)), num_bins)
        elif bins is not None:
            my_bins = bins
        else:
            my_bins = np.linspace(np.min(d), np.max(d), num_bins)
            # print(np.max(d))
        if density:
            weights = np.ones_like(d) / float(len(d))
            n, hist_bins, patches = plt.hist(d, weights=weights, cumulative=cumulative, bins=my_bins)
        else:
            n, hist_bins, patches = plt.hist(d, cumulative=cumulative, bins=bins)
        if density and log:
            type = 'log_pdf'
        elif density and not log:
            type = 'pdf'
        elif not density and log:
            type = 'log_histogram'
        else:
            type = 'histogram'
        if show_median:
            # print(d)
            plt.axvline(np.median(d), color='r', linestyle='dashed', linewidth=5)
        if fit_curve:
            x = np.arange(1, num_bins, 1)
            # Attempt 1 : Fit numpy logarithmic (exponential failed)
            # p = np.polyfit(np.log(x), n, 2)
            # print(p)
            # plt.plot(x, -p[0] *np.log(x) - p[1], color='g', ls='--', label = 'logarithmic')

            # Attempt 2 : Fit weibull
            k = 0.7
            l = np.mean(d ** k)
            plt.plot(x, weib(x, 2, k), color='r', ls='--', label='weibull')
        if show_legend:
            plt.legend()
        plt.plot()
        plt.title(f'{param} {type} over {num_agents} larvae')
        plt.xlabel(param)
        plt.ylabel('counts')
        filename = f'{param}_{type}_over_{num_agents}_larvae.jpg'
    return fig, filename


def spectogram(fig, axs, data, agent_ids, parameters, dt=None, Nsubplots=1, f_range=None, **kwargs):
    if len(agent_ids) != 1 or len(parameters) != 1:
        raise ('Currently spectogram is supported for a single agent and a single parameter')
    else:
        param = parameters[0]
        agent_id = agent_ids[0]
        agent_data = data[param].xs(agent_id, level='AgentID', drop_level=True)
    if dt:
        plt.xlabel('time(sec)')
        data.index.set_levels(data.index.levels[0] * dt, level=0, inplace=True)
    else:
        plt.xlabel('time(ticks)')
    plt.ylabel(f'Frequency of {param} (Hz)')
    plt.title(f'{param} spectrogram of {agent_id}')
    f, t, Sxx = signal.spectrogram(agent_data, fs=1 / dt)
    if f_range:
        fmin = f_range[0]  # Hz
        fmax = f_range[1]  # Hz
        freq_slice = np.where((f >= fmin) & (f <= fmax))

        # keep only frequencies of interest
        f = f[freq_slice]
        # print(Sxx.shape)
        # print(Sxx[:][1])
        Sxx = Sxx[freq_slice, :][0]
        # print(Sxx[:][1])
        # print(f[np.where(Sxx==np.nanmax(Sxx))[1]])
    plt.pcolormesh(t, f, Sxx)
    try:
        max_freq = np.round(f[np.where(Sxx == np.nanmax(Sxx))[0]][0], 3)
        plt.text(100, 2.5, f'Max power at {max_freq} Hz', {'color': 'white', 'fontsize': 10})
        print(max_freq)
    except:
        print('Not possible to detect frequency with maximum power')
        pass
    filename = f'{param}_spectrogram_of_{agent_id}.jpg'
    return fig, filename


def hist_mode(range, num_bins, figsize):
    dic = {'figsize': figsize,
           'density': 'True',
           'xlim': [range[0], range[1]],
           'bins': np.linspace(range[0], range[1], num_bins),
           'ylabel': 'probability, $P$'}
    return dic


def plot_stride_distribution(dataset, agent_id=None, save_to=None):
    d = dataset
    if agent_id is None:
        agent_id = d.agent_ids[0]

    if save_to is None:
        save_to = os.path.join(d.plot_dir, 'plot_stride_distribution')
    if not os.path.exists(save_to):
        os.makedirs(save_to)
    filepath = os.path.join(save_to, f'stride_distribution.{suf}')
    filepath_1 = os.path.join(save_to, f'stride_distribution_spatiotemporal.{suf}')
    filepath_2 = os.path.join(save_to, f'stride_distribution_spatial_hist.{suf}')

    agent_data = d.step_data.xs(agent_id, level='AgentID', drop_level=True)
    # l = d.endpoint_data['length'].loc[agent_id]

    s = agent_data['scaled_stride_dst'].dropna()
    t = agent_data['stride_dur'].dropna()
    # print(s)
    # print(t)
    fig, axs = plt.subplots(1, 1, figsize=([5, 5]))
    axs.plot(s, t, '.')
    axs.set_ylabel(r'duration, $(sec)$', fontsize=15)
    axs.set_xlabel(r'scal displacement', fontsize=15)
    fig.savefig(filepath_1, dpi=300)
    print(f'Image saved as {filepath_1}')

    fig, axs = plt.subplots(1, 1, figsize=([5, 5]))
    axs.hist(s, bins=20)
    axs.axvline(s.median(), color='red', linestyle='dashed', linewidth=1)
    # plt.plot(mean_spatial_stds, mean_temporal_stds)
    axs.set_ylabel(r'# strides', fontsize=15)
    axs.set_xlabel(r'scal displacement', fontsize=15)
    fig.savefig(filepath_2, dpi=300)
    print(f'Image saved as {filepath_2}')

    fig, axs = plt.subplots(1, 2, sharex=True, figsize=([10, 5]))
    axs = axs.ravel()

    axs[0].plot(s, t, '.')
    # plt.plot(mean_spatial_stds, mean_temporal_stds)
    axs[0].set_ylabel(r'duration, $(sec)$', fontsize=15)
    axs[0].set_xlabel(r'scal displacement', fontsize=15)

    axs[1].hist(s, bins=20)
    axs[1].axvline(s.median(), color='red', linestyle='dashed', linewidth=1)
    # plt.plot(mean_spatial_stds, mean_temporal_stds)
    axs[1].set_ylabel(r'# strides', fontsize=15)
    axs[1].set_xlabel(r'scal displacement', fontsize=15)

    plt.tight_layout()

    fig.savefig(filepath, dpi=300)
    print(f'Image saved as {filepath}')


def plot_stridechains(dataset, save_to=None):
    d = dataset

    if save_to is None:
        save_to = os.path.join(d.plot_dir, 'plot_stridechains')
    if not os.path.exists(save_to):
        os.makedirs(save_to)
    filepath_MLE = os.path.join(save_to, f'stridechain_distribution_MLE.{suf}')
    filepath_r = os.path.join(save_to, f'stridechain_distribution_r.{suf}')

    s = d.step_data[nam.length(nam.chain('stride'))].dropna()
    u, c = np.unique(s, return_counts=True)
    c = c / np.sum(c)
    c = 1 - np.cumsum(c)

    alpha = 1 + len(s) / np.sum(np.log(s))
    beta = len(s) / np.sum(s - 1)
    mu = np.mean(np.log(s))
    sigma = np.std(np.log(s))

    fig, axs = plt.subplots(1, 1, figsize=(10, 10), sharex=True, sharey=True)
    fig.suptitle('Stridechain distribution', fontsize=25)

    axs.loglog(u, c, 'or', label='stridechains')
    # axs.loglog(u, 1 - powerlaw_cdf_2(u, P[0], P[1]), 'k', lw=2, label='powerlaw linear')
    axs.loglog(u, 1 - powerlaw_cdf(u, 1, alpha), 'r', lw=2, label='powerlaw MLE')
    axs.loglog(u, 1 - exponential_cdf(u, 1, beta), 'g', lw=2, label='exponential MLE')
    axs.loglog(u, 1 - lognormal_cdf(u, mu, sigma), 'b', lw=2, label='lognormal MLE')

    axs.legend(loc='lower left', fontsize=15)
    axs.axis([1, np.max(s), 10 ** -4.0, 10 ** 0])
    # axs.text(25, 10 ** - 1.5, r'$\alpha=' + str(np.round(alpha * 100) / 100) + '$',
    #          {'color': 'k', 'fontsize': 16})

    plt.xlabel(r'Stridechain  length, $l$', fontsize=15)
    plt.ylabel(r'Probability Density, $P_l$', fontsize=15)

    fig.savefig(filepath_MLE, dpi=300)
    print(f'Image saved as {filepath_MLE}')

    fig, axs = plt.subplots(1, 1, figsize=(10, 10), sharex=True, sharey=True)
    fig.suptitle('Stridechain distribution', fontsize=25)

    axs.loglog(u, c, 'or', label='stridechains')

    for r in np.round(np.arange(0.8, 1, 0.025), 3):
        x = np.arange(1, np.max(s), 1)
        y = (1 - r) * r ** (x - 1)
        y = 1 - np.cumsum(y)
        plt.plot(x, y)
        plt.loglog(x, y, label=r)
        # plt.ylim(10 ** -4.5, 10 ** -0.2)
    # axs.loglog(u, 1 - pareto.cdf(u, b=my_b, loc=loc, scale=scale), 'y', lw=2, label=my_label)

    axs.legend(loc='lower left', fontsize=15)
    axs.axis([1, np.max(s), 10 ** -4.0, 10 ** 0])
    # axs.text(25, 10 ** - 1.5, r'$\alpha=' + str(np.round(alpha * 100) / 100) + '$',
    #          {'color': 'k', 'fontsize': 16})

    plt.xlabel(r'Stridechain  length, $l$', fontsize=15)
    plt.ylabel(r'Probability Density, $P_l$', fontsize=15)

    fig.savefig(filepath_r, dpi=300)
    print(f'Image saved as {filepath_r}')


def plot_bend_pauses(dataset, save_to=None):
    d = dataset
    if save_to is None:
        save_to = os.path.join(d.plot_dir, 'plot_bend_pauses')
    if not os.path.exists(save_to):
        os.makedirs(save_to)
    filepath = os.path.join(save_to, f'bend_pause_distribution.{suf}')

    s = d.step_data[nam.dur('bend_pause')].dropna()
    durmin, durmax = np.min(s), np.max(s)
    u, c, ccum = compute_density(s, durmin, durmax)
    alpha = 1 + len(s) / np.sum(np.log(s / durmin))
    beta = len(s) / np.sum(s - durmin)
    mu = np.mean(np.log(s))
    sigma = np.std(np.log(s))

    fig, axs = plt.subplots(1, 1, figsize=(10, 10), sharex=True, sharey=True)
    fig.suptitle('Bend-pause distribution', fontsize=25)

    axs.loglog(u, ccum, 'or', label='bend_pauses')
    axs.loglog(u, 1 - powerlaw_cdf(u, durmin, alpha), 'r', lw=2, label='powerlaw MLE')
    axs.loglog(u, 1 - exponential_cdf(u, durmin, beta), 'g', lw=2, label='exponential MLE')
    axs.loglog(u, 1 - lognormal_cdf(u, mu, sigma), 'b', lw=2, label='lognormal MLE')

    axs.legend(loc='lower left', fontsize=15)
    axs.axis([durmin, durmax, 10 ** -4.0, 10 ** 0])

    plt.xlabel(r'Bend pause duration, $(sec)$', fontsize=15)
    plt.ylabel(r'Probability Density, $P_d$', fontsize=15)

    fig.savefig(filepath, dpi=300)
    print(f'Image saved as {filepath}')


def plot_marked_strides(dataset, agent_ids=None, title=' ', show_legend=True, show_par_legend=False, slices=[],
                        return_fig=False):
    # We plot the complete or a slice of the timeseries of scal centroid velocity. The grey areas are stridechains
    d = dataset

    if agent_ids is None:
        agent_ids = d.agent_ids

    dir = 'epochs'
    save_to = os.path.join(d.plot_dir, dir)
    xx = 'marked_strides'
    this_suf = 'pdf'

    filepath_full = f'{xx}_full.{this_suf}'
    filepath_full_long = f'{xx}_full_long.{this_suf}'
    filepath_slices = []
    for i, slice in enumerate(slices):
        filepath_slices.append(f'{xx}_slice_{i}.{this_suf}')
    generic_filepaths = [filepath_full_long, filepath_full] + filepath_slices

    figsize_short = (20, 5)
    figsize_long = (15 * 6 * 3, 5)
    figsizes = [figsize_long, figsize_short] + [figsize_short] * len(generic_filepaths)

    xlims = [None, None] + slices

    ymax = 1.0

    dst = nam.scal('dst')
    v = nam.scal('vel')

    for agent_id in agent_ids:
        filepaths = [f'{agent_id}_{f}' for f in generic_filepaths]
        for figsize, filepath, xlim in zip(figsizes, filepaths, xlims):
            try:
                d.plot_step_data(parameters=[v], mode='time', figsize=figsize, agent_ids=[agent_id],
                                 ylabel=r'scal velocity, $v (sec^{-1})$', xlabel=r'time, $(sec)$', title=title,
                                 show_legend=show_legend,
                                 xlim=xlim,
                                 # ylim=[0.0, ymax],
                                 background_flags=[nam.id('stride')], background_for_chunks=['stride', 'non_stride'],
                                 legend_labels=['stride', 'pause'],
                                 marker_params=[nam.max(v), nam.min(v)],
                                 save_to=save_to, save_as=filepath)
            except:
                pass


def plot_marked_turns(dataset, agent_ids=None, turn_epochs=['Rturn', 'Lturn'],
                      vertical_boundaries=False, min_turn_angle=0, slices=[], return_fig=False):
    # We plot the complete or a slice of the timeseries of scal centroid velocity. The grey areas are stridechains
    d = dataset

    if agent_ids is None:
        agent_ids = d.agent_ids

    dir = 'epochs'
    save_to = os.path.join(d.plot_dir, dir)

    # if save_to is None:
    #     save_to = os.path.join(d.plot_dir, 'plot_strides')
    # if not os.path.exists(save_to):
    #     os.makedirs(save_to)
    # filepath_full = os.path.join(save_to, 'marked_strides_full_dur.pdf')
    xx = f'marked_turns_min_angle_{min_turn_angle}'
    filepath_full = f'{xx}_full.{suf}'
    filepath_full_long = f'{xx}_full_long.{suf}'
    filepath_slices = []
    for i, slice in enumerate(slices):
        filepath_slices.append(f'{xx}_slice_{i}.{suf}')
    generic_filepaths = [filepath_full_long, filepath_full] + filepath_slices

    # filepath_slice = os.path.join(save_to, f'marked_turns_slice_min_angle_{min_turn_angle}.pdf')
    # # filepath_full = 'marked_turns_full_dur.pdf'
    # filepath_full_long = os.path.join(save_to, f'marked_turns_full_min_angle_{min_turn_angle}.pdf')
    # filepaths=[filepath_slice, filepath_full_long]
    # filepath_slice_1 = 'marked_strides_slice_dur_1.pdf'
    # filepath_slice_2 = 'marked_strides_slice_dur_2.pdf'
    # filepath_slice_3 = 'marked_strides_slice_dur_3.pdf'

    figsize_short = (20, 5)
    figsize_long = (15 * 6, 5)
    figsizes = [figsize_long, figsize_short] + [figsize_short] * len(generic_filepaths)

    xlims = [None, None] + slices

    # ymax=1.0

    b = 'bend'
    bv = nam.vel(b)
    ho = 'front_orientation'
    hov = nam.vel(ho)

    for agent_id in agent_ids:
        filepaths = [f'{agent_id}_{f}' for f in generic_filepaths]

        s = d.step_data.xs(agent_id, level='AgentID', drop_level=True)
        # Nticks=len(s.index)
        # dur=Nticks/d.fr
        s.set_index(s.index.values / d.fr, inplace=True)

        b0 = s[b]
        bv0 = s[bv]
        ho0 = s[ho]
        hov0 = s[hov]

        for filepath, figsize, xlim in zip(filepaths, figsizes, xlims):
            fig, axs = plt.subplots(1, 1, figsize=figsize)

            if turn_epochs is not None:
                cmap = cm.get_cmap('Pastel2')
                num_chunks = len(turn_epochs)
                colors = [cmap(i) for i in np.arange(num_chunks)]
                epoch_handles = []
                for i, (chunk, color) in enumerate(zip(turn_epochs, colors)):
                    start_flag = f'{chunk}_start'
                    stop_flag = f'{chunk}_stop'
                    stop_indexes = s.index[s[stop_flag] == True]
                    start_indexes = s.index[s[start_flag] == True]
                    if min_turn_angle > 0:
                        angle_flag = nam.chunk_track(chunk, nam.unwrap('front_orientation'))
                        angles = np.abs(s[angle_flag].dropna().values)
                        stop_indexes = stop_indexes[angles > min_turn_angle]
                        start_indexes = start_indexes[angles > min_turn_angle]

                    for start, stop in zip(start_indexes, stop_indexes):
                        temp = plt.axvspan(start, stop, color=color, alpha=1.0)

                        if vertical_boundaries:
                            plt.axvline(start, color=f'{0.4 * (i + 1)}', alpha=0.6, linestyle='dashed', linewidth=1)
                            plt.axvline(stop, color=f'{0.4 * (i + 1)}', alpha=0.6, linestyle='dashed', linewidth=1)
                    epoch_handles.append(temp)
            ax1 = b0.plot(label=r'$\theta_{b}$', lw=2, color='blue')
            ax1.set_ylabel(r'angle $(deg)$')
            ax1.set_xlabel(r'time $(sec)$')
            ax1.set_ylim([-100, 100])
            ax1.set_xlim(xlim)
            # plt.legend(loc= 'upper left')
            ax2 = bv0.plot(secondary_y=True, label=r'$\dot{\theta}_{b}$', lw=2, color='green')
            ax2.plot(hov0, label=r'$\dot{\theta}_{or}$', lw=3, color='black')
            ax2.set_ylabel(r'angular velocity $(deg/sec)$')
            ax2.set_ylim([-500, 500])

            plt.axhline(0, color='black', alpha=0.4, linestyle='dashed', linewidth=1)

            handles, labels = [], []
            for ax in fig.axes:
                for h, l in zip(*ax.get_legend_handles_labels()):
                    handles.append(h)
                    labels.append(l)

            # plt.legend(handles, labels, loc='upper left')

            par_legend = plt.legend(handles, labels, loc=2)
            plt.legend(epoch_handles, turn_epochs, loc=1)
            plt.gca().add_artist(par_legend)
            plt.subplots_adjust(hspace=0.05, top=0.96, bottom=0.15, left=0.06, right=0.95)
            fig.savefig(f'{save_to}/{filepath}', dpi=300)
            print(f'Image saved as {filepath}')


def plot_velocity_spect_hist(dataset, agent_id=None,
                             titles=['scal velocity spectogram', 'scal velocity histogram'], return_fig=False):
    # We plot the complete or a slice of the timeseries of scal centroid velocity. The grey areas are stridechains
    d = dataset

    # if save_to is None:
    #     save_to = os.path.join(d.plot_dir, 'plot_strides')
    # if not os.path.exists(save_to):
    #     os.makedirs(save_to)
    # filepath_full = os.path.join(save_to, 'marked_strides_full_dur.pdf')
    # filepath_slice = os.path.join(save_to, 'marked_strides_slice_dur.pdf')

    figsize_spect = (6, 5)
    figsize_hist = (5, 5)

    v = nam.scal(d.velocity)

    if agent_id is None:
        for i, id in enumerate(d.agent_ids):
            filepath_spect = f'velocity_spectogram_of_{id}.{suf}'
            d.plot_step_data(parameters=[v], mode='spect', agent_ids=[id],
                             ylabel=r'frequency, $(Hz)$', xlabel=r'time, $(sec)$', figsize=figsize_spect,
                             title=titles[0], f_range=[0, 6], save_as=filepath_spect)

            filepath_hist = f'velocity_histogram_of_{id}.{suf}'
            d.plot_step_data(parameters=[v], mode='hist', agent_ids=[id],
                             ylabel=r'Probability Density, $P_v$', xlabel=r'scal velocity, $v (sec^{-1})$',
                             xlim=[0, 0.8], ylim=[0, 0.05], density=True, bins=np.linspace(0, 6, 500),
                             figsize=figsize_hist,
                             title=titles[0], save_as=filepath_hist)

    else:
        filepath_spect = f'velocity_spectogram_of_{agent_id}.{suf}'
        d.plot_step_data(parameters=[v], mode='spect', agent_ids=[agent_id],
                         ylabel=r'frequency, $(Hz)$', xlabel=r'time, $(sec)$', figsize=figsize_spect,
                         title=titles[0], f_range=[0, 6], save_as=filepath_spect)

        filepath_hist = f'velocity_histogram_of_{agent_id}.{suf}'
        d.plot_step_data(parameters=[v], mode='hist', agent_ids=[agent_id],
                         ylabel=r'Probability Density, $P_v$', xlabel=r'scal velocity, $v (1/sec)$',
                         xlim=[0, 0.8], ylim=[0, 0.05], density=True, bins=np.linspace(0, 6, 500), figsize=figsize_hist,
                         title=titles[0], save_as=filepath_hist)


def plot_strides(dataset, agent_id=None, radius_in_sec=None, save_as=f'parsed_strides.{suf}', save_to=None,
                 return_fig=False):
    d = dataset
    if agent_id is None:
        agent_id = d.agent_ids[0]
    if radius_in_sec is None:
        freq = nam.freq(nam.scal(d.velocity))
        radius_in_sec = (1 / d.endpoint_data.loc[agent_id, freq]) / 2
    r = radius_in_sec

    if save_to is None:
        save_to = os.path.join(d.plot_dir, 'plot_strides')
    if not os.path.exists(save_to):
        os.makedirs(save_to)

    b = 'bend'
    to = 'rear_orientation'
    ho = 'front_orientation'
    bv = nam.vel(b)
    tov = nam.vel(to)
    hov = nam.vel(ho)
    ba = nam.acc(b)
    toa = nam.acc(to)
    hoa = nam.acc(ho)
    ds = d.distance
    v = d.velocity
    a = d.acceleration
    sds = nam.scal(ds)
    sv = nam.scal(v)
    sa = nam.scal(a)
    stride_flag = nam.max(sv)

    dim_x, dim_y = 18, 5
    fig_x, fig_y = dim_x * 100, dim_y * 100
    figsize = (fig_x, fig_y)
    size = (fig_x, fig_y * 13)
    long_time_figsize = (dim_x, dim_y)

    l_angle = 'radians $(deg)$'
    l_angvel = 'angular velocity $(deg/sec)$'
    l_angacc = 'angular acceleration, $(deg^2/sec)$'
    l_time = 'time $(sec)$'
    l_dst = 'distance $(mm)$'
    l_vel = 'velocity $(mm/sec)$'
    l_acc = 'acceleration $(mm/sec^2)$'
    l_sc_dst = 'scal distance $(-)$'
    l_sc_vel = 'scal velocity $(sec^{-1})$'
    l_sc_acc = 'scal acceleration $(sec^{-2})$'

    y_min, y_max = -4, 4
    d.plot_step_data(agent_ids=[agent_id], parameters=[sa], title='scal acceleration during strides',
                     mode='parsed_time', figsize=long_time_figsize,
                     ylabel=l_sc_acc, xlabel=l_time,
                     xlim=None, plot_quantiles=7,
                     center_flag=stride_flag, radius_in_sec=r, ylim=([y_min, y_max]),
                     save_to=save_to,
                     save_as=f'01_scaled_acceleration_during_strides.{suf}')

    y_min, y_max = 0.0, 0.8
    d.plot_step_data(agent_ids=[agent_id], parameters=[sv], title='scal velocity during strides',
                     mode='parsed_time', figsize=long_time_figsize,
                     ylabel=l_sc_vel, xlabel=l_time,
                     xlim=None, plot_quantiles=7,
                     center_flag=stride_flag, radius_in_sec=r, ylim=([y_min, y_max]),
                     save_to=save_to,
                     save_as=f'02_scaled_velocity_during_strides.{suf}')

    y_min, y_max = 0.0, 0.3
    d.plot_step_data(agent_ids=[agent_id], parameters=[sds], title='scal displacement during strides',
                     mode='parsed_time', figsize=long_time_figsize,
                     ylabel=l_sc_dst, xlabel=l_time,
                     xlim=None, plot_quantiles=7, cumulative=True,
                     center_flag=stride_flag, radius_in_sec=r, ylim=([y_min, y_max]),
                     save_to=save_to,
                     save_as=f'03_scaled_displacement_during_strides.{suf}')

    y_min, y_max = -15, 15
    d.plot_step_data(agent_ids=[agent_id], parameters=[a], title='acceleration during strides',
                     mode='parsed_time', figsize=long_time_figsize,
                     ylabel=l_acc, xlabel=l_time,
                     xlim=None, plot_quantiles=7,
                     center_flag=stride_flag, radius_in_sec=r, ylim=([y_min, y_max]),
                     save_to=save_to,
                     save_as=f'04_acceleration_during_strides.{suf}')

    y_min, y_max = 0.0, 4.0
    d.plot_step_data(agent_ids=[agent_id], parameters=[v], title='velocity during strides',
                     mode='parsed_time', figsize=long_time_figsize,
                     ylabel=l_vel, xlabel=l_time,
                     xlim=None, plot_quantiles=7,
                     center_flag=stride_flag, radius_in_sec=r, ylim=([y_min, y_max]),
                     save_to=save_to,
                     save_as=f'05_velocity_during_strides.{suf}')

    y_min, y_max = 0.0, 1.5
    d.plot_step_data(agent_ids=[agent_id], parameters=[ds], title='displacement during strides',
                     mode='parsed_time', figsize=long_time_figsize,
                     ylabel=l_dst, xlabel=l_time,
                     xlim=None, plot_quantiles=7, cumulative=True,
                     center_flag=stride_flag, radius_in_sec=r, ylim=([y_min, y_max]),
                     save_to=save_to,
                     save_as=f'06_displacement_during_strides.{suf}')

    y = 1200
    d.plot_step_data(agent_ids=[agent_id], parameters=[ba], title='body bend acceleration during strides',
                     mode='parsed_time', figsize=long_time_figsize,
                     ylabel=l_angacc, xlabel=l_time,
                     xlim=None, plot_quantiles=7,
                     center_flag=stride_flag, radius_in_sec=r, ylim=([-y, y]),
                     save_to=save_to,
                     save_as=f'07_body_bend_acc_during_strides.{suf}')

    y = 150
    d.plot_step_data(agent_ids=[agent_id], parameters=[bv], title='body bend velocity during strides',
                     mode='parsed_time', figsize=long_time_figsize,
                     ylabel=l_angvel, xlabel=l_time,
                     xlim=None, plot_quantiles=7,
                     center_flag=stride_flag, radius_in_sec=r, ylim=([-y, y]),
                     save_to=save_to,
                     save_as=f'08_body_bend_vel_during_strides.{suf}')

    y = 30
    d.plot_step_data(agent_ids=[agent_id], parameters=[b], title='body bend during strides',
                     mode='parsed_time', figsize=long_time_figsize,
                     ylabel=l_angle, xlabel=l_time,
                     xlim=None, plot_quantiles=7,
                     center_flag=stride_flag, radius_in_sec=r, ylim=([-y, y]),
                     save_to=save_to,
                     save_as=f'09_body_bend_during_strides.{suf}')

    y = 1200
    d.plot_step_data(agent_ids=[agent_id], parameters=[hoa], title='head reorientation acceleration during strides',
                     mode='parsed_time', figsize=long_time_figsize,
                     ylabel=l_angacc, xlabel=l_time,
                     xlim=None, plot_quantiles=7,
                     center_flag=stride_flag, radius_in_sec=r, ylim=([-y, y]),
                     save_to=save_to,
                     save_as=f'10_head_orient_acc_during_strides.{suf}')

    y = 150
    d.plot_step_data(agent_ids=[agent_id], parameters=[hov], title='head reorientation velocity during strides',
                     mode='parsed_time', figsize=long_time_figsize,
                     ylabel=l_angvel, xlabel=l_time,
                     xlim=None, plot_quantiles=7,
                     center_flag=stride_flag, radius_in_sec=r, ylim=([-y, y]),
                     save_to=save_to,
                     save_as=f'11_head_orient_vel_during_strides.{suf}')

    y = 250
    d.plot_step_data(agent_ids=[agent_id], parameters=[toa],
                     title='rear-half reorientation acceleration during strides',
                     mode='parsed_time', figsize=long_time_figsize,
                     ylabel=l_angacc, xlabel=l_time,
                     xlim=None, plot_quantiles=7,
                     center_flag=stride_flag, radius_in_sec=r, ylim=([-y, y]),
                     save_to=save_to,
                     save_as=f'12_rear_half_orient_acc_during_strides.{suf}')

    y = 30
    d.plot_step_data(agent_ids=[agent_id], parameters=[tov], title='rear-half reorientation velocity during strides',
                     mode='parsed_time', figsize=long_time_figsize,
                     ylabel=l_angvel, xlabel=l_time,
                     xlim=None, plot_quantiles=7,
                     center_flag=stride_flag, radius_in_sec=r, ylim=([-y, y]),
                     save_to=save_to,
                     save_as=f'13_rear_half_orient_vel_during_strides.{suf}')

    combine_images(filenames=None, file_dir=save_to, save_as=save_as, save_to=save_to, size=size, figsize=figsize)


def plot_pauses(dataset, Npauses=10, save_to=None, plot_simulated=False, return_fig=False):
    if save_to is None:
        save_to = dataset.plot_dir
    dt = dataset.dt
    filename1 = f'pauses.{suf}'
    filepath1 = os.path.join(save_to, filename1)
    filename2 = f'pause_max_hist.{suf}'
    filepath2 = os.path.join(save_to, filename2)
    if not plot_simulated:
        exp_bends, exp_bendvels = dataset.load_pause_dataset(load_simulated=False)
        sim = False
    else:
        exp_bends, exp_bendvels, sim_bends, sim_bendvels, sim_acts = dataset.load_pause_dataset(load_simulated=True)
        sim = True

    bend_r, bendvel_r = 180, 600
    lengths = (~np.isnan(exp_bends)).sum(1)
    sel_ind = lengths.argsort()[-Npauses:][::-1]
    sel_exp_bends = [exp_bends[i] for i in sel_ind]
    sel_exp_bendvels = [exp_bendvels[i] for i in sel_ind]
    max_dur = np.max(lengths)
    x = np.arange(0, max_dur, int(0.5 / dt))
    if sim:
        sel_sim_bends = [sim_bends[i] for i in sel_ind]
        sel_sim_bendvels = [sim_bendvels[i] for i in sel_ind]
        sel_sim_acts = [sim_acts[i] for i in sel_ind]

    fig, axs = plt.subplots(Npauses, 1, figsize=(15, Npauses * 3), sharex=True, sharey=True)
    axs = axs.ravel()
    axs_l, axs_r = [], []
    for i in range(Npauses):
        ax_l = axs[i]
        ax_r = ax_l.twinx()
        axs_l.append(ax_l)
        axs_r.append(ax_r)

    # share the secondary axes
    for ax in axs_r[1:]:
        axs_r[0].get_shared_y_axes().join(axs_r[0], ax)

    for i in range(Npauses):
        eb = sel_exp_bends[i]
        ebv = sel_exp_bendvels[i]
        axs_l[i].plot(eb, 'r', label='observed bending angle')
        axs_r[i].plot(ebv, 'b', label='observed bending velocity')

        if sim:
            sb = sel_sim_bends[i]
            sbv = sel_sim_bendvels[i]
            sa = sel_sim_acts[i]
            axs_l[i].plot(sb, 'r', linestyle='dashed', label='simulated bending angle')
            axs_r[i].plot(sb, 'b', linestyle='dashed', label='simulated bending velocity')
        axs_l[i].axhline(0, color='green', alpha=0.5, linestyle='dashed', linewidth=1)
        axs_l[i].set_ylabel('angle (deg)')
        axs_l[i].set_ylim([-bend_r, bend_r])
        axs_r[i].set_ylabel('angular velocity (deg/sec)')
        axs_r[i].set_ylim([-bendvel_r, bendvel_r])
        axs_l[i].legend(loc='upper left')
        axs_r[i].legend(loc='upper right')
    axs_l[-1].set_xticks(x)
    axs_l[-1].set_xticklabels([i * dt for i in x])
    axs_l[-1].set_xlim([0, max_dur])
    axs_l[-1].set_xlabel('time(sec)', fontsize=15)
    plt.subplots_adjust(hspace=0.05, top=0.96, bottom=0.02, left=0.07, right=0.93)
    fig.suptitle('Individual pauses', fontsize=25)
    save_plot(fig, filepath1, filename1)

    # Plot max values histogram
    max_bends, max_bendvels = [np.round(np.nanmax(np.abs(p), axis=0)) for p in [exp_bends, exp_bendvels]]
    fig, axs = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
    axs = axs.ravel()
    Nbins = 50
    axs[0].hist(max_bends, color='g', bins=Nbins, label='maximum bend')
    axs[0].set_xlabel('angle (deg)')
    axs[0].set_ylabel('counts')
    axs[1].hist(max_bendvels, color='r', bins=Nbins, label='maximum bending velocity')
    axs[1].set_xlabel('angular velocity (deg/s)')
    axs[1].set_ylabel('counts')
    fig.suptitle('Maximum values during pauses', fontsize=20)
    save_plot(fig, filepath2, filename2)


def plot_debs(deb_dicts=None, save_to=None, save_as=None, mode='full', roversVSsitters=False, sim_only=False,
              start_at_sim_start=False, time_unit='hours', return_fig=False,
              datasets=None, labels=None, include_default_deb=False):
    from lib.model.agents.deb import deb_dict, deb_default
    warnings.filterwarnings('ignore')
    if save_to is None:
        save_to = DebFolder
    os.makedirs(save_to, exist_ok=True)
    if save_as is None:
        save_as = f'debs.{suf}'
    # filepath = os.path.join(save_to, save_as)
    if deb_dicts is None:
        default_deb_added = False
        deb_dicts = []
        for d, l in zip(datasets, labels):
            starvation_hours = d.config['starvation_hours']
            if include_default_deb and not default_deb_added:
                f = d.config['deb_base_f']
                deb_model = deb_default(starvation_hours=starvation_hours, base_f=f)
                deb_dicts.append(deb_model)
            dataset_deb_dicts = [deb_dict(d, id, starvation_hours=starvation_hours) for id in d.agent_ids]
            deb_dicts.append(dataset_deb_dicts)
        deb_dicts = flatten_list(deb_dicts)

    Ndebs = len(deb_dicts)
    ids = [d['id'] for d in deb_dicts]
    if Ndebs == 1:
        cols = [(0, 1, 0.1)]
        leg_ids = ids
        leg_cols = cols
    elif roversVSsitters:
        cols = []
        temp_id = None
        for id in ids:
            if str.startswith(id, 'Rover'):
                cols.append((0, 0, 1))
            elif str.startswith(id, 'Sitter'):
                cols.append((1, 0, 0))
            else:
                cols.append((0, 1, 0.1))
                temp_id = id
        if temp_id is not None:
            leg_cols = [(0, 1, 0.1), (0, 0, 1), (1, 0, 0)]
            leg_ids = [temp_id, 'Rovers', 'Sitters']
        else:
            leg_cols = [(0, 0, 1), (1, 0, 0)]
            leg_ids = ['Rovers', 'Sitters']
    else:
        cols = [(0.9 - i, 0.1 + i, 0.1) for i in np.linspace(0, 0.9, Ndebs)]
        leg_ids = ids
        leg_cols = cols

    labels0 = ['mass', 'length',
               'reserve', 'f',
               'reserve_density', 'hunger',
               'puppation_buffer', 'explore2exploit_balance',
               'f_filt']
    ylabels0 = ['wet mass $(mg)$', 'body length $(mm)$',
                r'reserve $(J)$', r'functional response $(-)$',
                r'reserve density $(-)$', r'hunger drive $(-)$',
                r'pupation buffer $(-)$', r'explore2exploit_balance $(-)$',
                r'functional response $(-)$', ]
    if mode == 'minimal':
        idx = [2, 4, 5, 6]
    elif mode == 'hunger':
        idx = [2, 4, 5, 7, 8]
    elif mode == 'f':
        idx = [3]
    elif mode == 'full':
        idx = [0, 1, 2, 6]
    elif mode == 'complete':
        idx = [0, 1, 2, 4, 5, 6]
    labels = [labels0[i] for i in idx]
    ylabels = [ylabels0[i] for i in idx]

    figsize = (15, 4 * len(labels))
    fig, axs = plt.subplots(len(labels), figsize=figsize, sharex=True)
    if len(labels) > 1:
        axs = axs.ravel()
    else:
        axs = [axs]
    t0s, t1s, t2s, ages = [], [], [], []
    for d, id, c in zip(deb_dicts, ids, cols):
        Nticks = len(d[labels[0]])
        t0, t1, t2, t3, age = d['birth'], d['puppation'], d['death'], d['sim_start'], d['age']
        if time_unit == 'hours':
            pass
        elif time_unit == 'minutes':
            t0 *= 60
            t1 *= 60
            t2 *= 60
            t3 *= 60
            age *= 60
        elif time_unit == 'seconds':
            t0 *= 3600
            t1 *= 3600
            t2 *= 3600
            t3 *= 3600
            age *= 3600
        if d['simulation']:
            if not start_at_sim_start:
                s0, s1 = t0 + t3, age
            else:
                s0, s1 = 0, age - t0 - t3
        else:
            s0, s1 = 0, age

        t_deb = np.linspace(s0, s1, Nticks)
        starvation = d['starvation']
        t0s.append(t0)
        t1s.append(t1)
        t2s.append(t2)
        ages.append(age)
        # print(starvation)
        # print(t0, t3, t0+t3)

        for j, (l, yl) in enumerate(zip(labels, ylabels)):
            if l == 'f_filt':
                P = d['f']
                sos = butter(N=1, Wn=4, btype='lowpass', analog=False, fs=Nticks / (s1 - s0), output='sos')
                P = sosfiltfilt(sos, P)
            else:
                P = d[l]
            ax = axs[j]
            ax.plot(t_deb, P, color=c, label=id, linewidth=2, alpha=1.0)
            ax.axvline(t0, color=c, alpha=0.6, linestyle='dashdot', linewidth=3)
            # b1 = plt.axvline(t0, color=c, alpha=0.2, linestyle='dashdot', linewidth=3)
            ax.axvline(t1, color=c, alpha=0.6, linestyle='dashdot', linewidth=3)
            ax.axvline(t2, color=c, alpha=0.6, linestyle='dashdot', linewidth=3)
            if sim_only:
                ax.set_xlim(s0, s1)
            # else :
            #     ax.set_xlim(xmin=s0)
            for st0, st1 in starvation:
                if start_at_sim_start and d['simulation']:
                    st0 -= (t0 + t3)
                    st1 -= (t0 + t3)
                ax.axvspan(st0, st1, color=c, alpha=0.2)
            # b2 = plt.axvline(t1, color=c, alpha=0.2, linestyle='dashdot', linewidth=3)
            # b_leg = plt.legend([b1, b2], ["birth", "puppation"], loc='upper center')
            # plt.gca().add_artist(b_leg)
            ax.set_ylabel(yl)
            ax.yaxis.set_major_locator(ticker.MaxNLocator(3))
            ax.xaxis.set_major_locator(ticker.MaxNLocator(10))
            # ax.ticklabel_format(useMathText=True, scilimits=(0, 0))
            if l in ['puppation_buffer', 'explore2exploit_balance']:
                ax.set_ylim([0, 1])
            if l == 'f':
                ax.axhline(np.nanmean(P), color=c, alpha=0.6, linestyle='dashed', linewidth=2)
                ax.set_ylim(ymin=0)

        for t in [t0, t1, t2]:
            if not np.isnan(t):
                try:
                    ax.annotate('', xy=(t, 0), xycoords='data',
                                xytext=(t, -0.2), textcoords='data',
                                arrowprops=dict(color='black', shrink=0.1, alpha=0.6)
                                )
                except:
                    pass
    ax.set_xlabel(f'time $({time_unit})$')
    T0 = np.nanmean(t0s)
    T1 = np.nanmean(t1s)
    T2 = np.nanmean(t2s)
    fontsize = 15
    y = -0.2
    texts = ['hatch', 'pupation', 'death']
    # texts=['egg', 'hatch', 'pupation', 'death']
    text_xs = [T0, T1, T2]
    # text_xs=[0, T0, T1, T2]
    for text, x in zip(texts, text_xs):
        try:
            ax.annotate(text, xy=(x, 0), xycoords='data', fontsize=fontsize,
                        xytext=(x, y), textcoords='data',
                        horizontalalignment='center', verticalalignment='top')
        except:
            pass

    axs[0].legend(handles=[mpatches.Patch(color=c, label=id) for c, id in zip(leg_cols, leg_ids)],
                  labels=leg_ids, fontsize=20, loc='upper left', prop={'size': 15})
    fig.subplots_adjust(top=0.95, bottom=0.15, left=0.1, right=0.93, hspace=0.02)
    return process_plot(fig, save_to, save_as, return_fig)


def plot_surface(x, y, z, labels, z0=None, title=None, save_to=None, save_as=None, pref=None):
    fig = plt.figure(figsize=(20, 10))
    if title is not None:
        fig.suptitle(title)
    # ax = fig.gca(projection='3d')
    # ax = fig.add_subplot(111, projection='3d')
    ax = Axes3D(fig)
    ax.plot_surface(x, y, z,
                    cmap=cm.coolwarm,
                    linewidth=0,
                    antialiased=True)
    if z0 is not None:
        ax.plot_surface(x, y, np.ones(x.shape) * z0, alpha=0.5)
    ax.set_xlabel(labels[0])
    ax.set_ylabel(labels[1])
    ax.set_zlabel(labels[2])

    ax.xaxis.set_major_locator(ticker.MaxNLocator(5))
    ax.yaxis.set_major_locator(ticker.MaxNLocator(5))
    ax.zaxis.set_major_locator(ticker.MaxNLocator(5))

    if save_to is not None:
        os.makedirs(save_to, exist_ok=True)
        if save_as is None:
            save_as = f'surface.{suf}'
            if pref is not None:
                save_as = f'{pref}_{save_as}'
        filepath = os.path.join(save_to, save_as)
        fig.savefig(filepath, dpi=300)
        print(f'Surface saved as {save_as}')
    return ax


def plot_heatmap(x, y, z, labels, title=None, save_to=None, save_as=None, pref=None):
    # fig = plt.figure(figsize=(10, 5))
    axs = sns.heatmap(z, annot=True, fmt="g", cmap=cm.coolwarm,
                      xticklabels=x.tolist(), yticklabels=y.tolist(),
                      cbar_kws={"orientation": "vertical",
                                'label': labels[2],
                                # 'ticks': [1, 0, -1]
                                })
    axs.xaxis.set_major_locator(ticker.MaxNLocator(4))
    axs.yaxis.set_major_locator(ticker.MaxNLocator(4))
    axs.xaxis.set_ticks_position('top')
    # ax.yaxis.set_major_locator(ticker.MultipleLocator(5))
    # ax.yaxis.set_major_formatter(ticker.ScalarFormatter())
    # ax.set_size_cm(3.5, 3.5)
    # cax = plt.gcf().axes[-1]
    # cax.xaxis.set_major_locator(ticker.MaxNLocator(4))

    # ax.set_yticklabels(ax.get_yticklabels(), rotation=0)
    axs.set_ylabel(labels[1])
    axs.set_xlabel(labels[0])
    if title is not None:
        axs.set_suptitle(title, fontsize=20)

    if save_to is not None:
        os.makedirs(save_to, exist_ok=True)
        if save_as is None:
            save_as = f'heatmap.{suf}'
            if pref is not None:
                save_as = f'{pref}_{save_as}'
        filepath = os.path.join(save_to, save_as)
        plt.savefig(filepath, dpi=300)
        print(f'Heatmap saved as {filepath}')
    return axs


def plot_3pars(df, labels, save_to, z0=None, pref=None):
    x, y = np.unique(df[labels[0]].values), np.unique(df[labels[1]].values)
    X, Y = np.meshgrid(x, y)

    z = df[labels[2]].values.reshape(X.shape).T

    plot_heatmap(x, y, z, labels, save_to=save_to, pref=pref)
    plot_surface(X, Y, z, labels, save_to=save_to, z0=z0, pref=pref)
    plt.close('all')


def plot_bend2orientation_analysis(dataset, save_to=None, save_as=f'bend2orientation.{suf}'):
    d = dataset
    s = d.step_data
    if save_to is None:
        # save_to = os.path.join(self.plot_dir, 'fit_dataset')
        save_to = dataset.plot_dir
    # if not os.path.exists(save_to):
    #     os.makedirs(save_to)
    filepath = os.path.join(save_to, save_as)

    # s = self.step_data
    avels = nam.vel(d.angles)
    if not set(avels).issubset(s.columns.values):
        raise ValueError('Spineangle angular velocities do not exist in step_data')
    hov = nam.vel('front_orientation')
    N = d.Nangles
    k = range(N)
    s = s.loc[s[avels].dropna().index.values].copy()
    target = s[hov].dropna()
    num_best = 5
    combos = []
    corrs = []
    ps = []
    for i in k[:-5]:
        for c in itertools.combinations(avels, i + 1):
            # for c in itertools.combinations(avels, i + 1):
            tseries = s[list(c)].dropna().sum(axis=1)
            r, p = stats.pearsonr(target, tseries)
            combos.append(c)
            corrs.append(r)
            ps.append(p)
    max_corrs = heapq.nlargest(num_best, corrs)
    max_corrs_idx = heapq.nlargest(num_best, range(len(corrs)), key=corrs.__getitem__)
    best_combos = [combos[i] for i in max_corrs_idx]
    best_combos_ind = [np.sort([avels.index(x) + 1 for x in set(avels).intersection(c)]) for c in best_combos]
    best_combo = combos[heapq.nlargest(1, range(len(corrs)), key=corrs.__getitem__)[0]]

    # best_combos_ind[0]=[1,2,3,4,5]
    # best_combos_ind[1]=[1,2,3,4]
    # best_combos_ind[2]=[1,2,3,4,7]
    # best_combos_ind[3]=[1,3]
    # best_combos_ind[4]=[1,2,3]
    for i, (cor, combo) in enumerate(zip(max_corrs, best_combos_ind)):
        print(f'Combo number {i} has correlation {cor}')
        print(f'Includes {combo}')
        print()
    print(f'Best combo is : {best_combo}')

    X0 = s[avels].dropna().values
    y = target.values

    figsize = (15, 7)

    # Plot figure with subplots of different sizes
    fig = plt.figure(figsize=figsize)
    fig, axs = plt.subplots(1, 2, figsize=figsize)
    axs = axs.ravel()
    # set up subplot grid
    # gridspec.GridSpec(2, 2)

    # plt.subplot2grid((2, 2), (0, 0), colspan=1, rowspan=1)

    scores1 = []
    coefs1 = []
    for i in k:
        X = X0[:, i:i + 1]
        reg = LinearRegression().fit(X, y)
        scores1.append(reg.score(X, y))
        coefs1.append(reg.coef_)
    # fig.suptitle('Reorientation prediction by cum angles')
    axs[0].scatter(np.arange(1, N + 1), scores1, c='blue', alpha=1.0, marker=",", label='single', s=200)
    axs[0].plot(np.arange(1, N + 1), scores1, c='blue')
    axs[0].set_xticks(ticks=np.arange(1, N + 1))
    axs[0].set_xlabel(r'angular velocity, $\dot{\theta}_{i}$')
    axs[0].set_ylabel('regression score')

    # plt.subplot2grid((2, 2), (0, 1), colspan=1, rowspan=1)

    scores2 = []
    coefs2 = []
    for i in k:
        X = X0[:, 0:i + 1]
        reg = LinearRegression().fit(X, y)
        scores2.append(reg.score(X, y))
        coefs2.append(reg.coef_)
    # fig.suptitle('Reorientation prediction by each spineangle')
    axs[0].scatter(np.arange(1, N + 1), scores2, c='green', alpha=1.0, marker="o", label='cumulative', s=200)
    axs[0].plot(np.arange(1, N + 1), scores2, c='green')
    shape1 = patches.Circle((0, 0), 1, facecolor='blue')
    shape2 = patches.Rectangle((0, 0), 1, 1, facecolor='green')
    axs[0].legend(loc='lower left')
    # axs[0].legend((shape1, shape2), ('single', 'cumulative'), loc='lower left')
    axs[0].yaxis.set_major_locator(ticker.MaxNLocator(4))
    # r = np.arange(1, N + 1)
    # plt.xticks(ticks=r, labels=['1'] + [f'1-{i}' for i in r[1:]])
    # plt.xlabel(r'cumulative angular velocity, $\dot{\theta}_{1-i}$')
    # plt.ylabel('regression score')

    # plt.subplot2grid((2, 2), (1, 0), colspan=2, rowspan=1)

    ylim = [0.6, 1]
    axs[1].bar(x=[','.join(map(str, c)) for c in best_combos_ind], height=max_corrs, width=0.8, color='black')
    # ax.set_xticks(best_combos_ind)
    axs[1].set_xlabel('combined angular velocities')
    axs[1].set_ylabel('Pearson correlation')
    axs[1].tick_params(axis='x', which='major', labelsize=15)
    axs[1].set_ylim(ylim)
    axs[1].yaxis.set_major_locator(ticker.MaxNLocator(4))
    plt.subplots_adjust(wspace=0.3, left=0.1, right=0.95, bottom=0.15, top=0.95)
    fig.savefig(filepath, dpi=300)
    print(f'Image saved as {filepath}')
    return best_combo


def plot_sliding_window_analysis(dataset, parameter, flag, radius_in_sec, save_to=None):
    d = dataset
    if save_to is None:
        save_to = os.path.join(d.plot_dir, 'plot_strides')
    if not os.path.exists(save_to):
        os.makedirs(save_to)
    filepath = os.path.join(save_to, f'{parameter}_around_{flag}_offset_analysis.{suf}')
    radius_in_ticks = np.ceil(radius_in_sec / d.dt)

    parsed_data_dir = f'{d.data_dir}/{parameter}_around_{flag}'
    file_description_path = os.path.join(parsed_data_dir, 'filename_description.csv')
    file_description = pd.read_csv(file_description_path, index_col=0, header=0)
    file_description = file_description[flag].dropna()
    offsets_in_ticks = file_description.index.values
    offsets_in_sec = np.round(offsets_in_ticks * d.dt, 3)
    means = []
    stds = []
    for offset in offsets_in_ticks:
        print(offset)
        data_filename = file_description.loc[offset]
        # print(data_filename)
        data_file_path = os.path.join(parsed_data_dir, data_filename)
        # print(data_file_path)

        segments = pd.read_csv(data_file_path, index_col=[0, 1], header=0)

        d = segments.droplevel('AgentID')
        # We plot distance so we prefer a cumulative plot
        d = d.T.cumsum().T
        tot_dsts = d.iloc[:, -1]
        mean = np.nanmean(tot_dsts)
        std = np.nanstd(tot_dsts)
        # print(f'mean : {mean}, std : {std}')
        means.append(mean)
        stds.append(std)

    fig, axs = plt.subplots(2, 1, figsize=(10, 10), sharex=True)
    plt.rc('text', usetex=True)
    font = {'size': 15}
    plt.rc('font', **font)
    plt.rc('legend', **{'fontsize': 12})
    fig.suptitle('Scaled displacement per stride ', fontsize=25)
    fig.subplots_adjust(top=0.94, bottom=0.15, hspace=0.06)

    axs[0].scatter(np.arange(len(means)), means, marker='o', color='r', label='mean')
    # axs[0].set_title('Mean', fontsize=15)

    axs[1].scatter(np.arange(len(stds)), stds, marker='o', color='g', label='std')
    # axs[1].set_title('Standard deviation', fontsize=15)
    plt.xticks(ticks=np.arange(len(offsets_in_sec)), labels=offsets_in_sec)
    axs[1].set_xlabel('offset from velocity maximum, $sec$', fontsize=15)
    axs[0].set_ylabel('length fraction', fontsize=15)
    axs[1].set_ylabel('length fraction', fontsize=15)
    # axs[0].set_ylim([0.215, 0.235])
    # axs[1].set_ylim([0.04, 0.06])
    axs[0].legend(loc="upper right")
    axs[1].legend(loc="upper right")
    index_min_std = stds.index(min(stds))
    optimal_flag_phase_in_rad = 2 * np.pi * index_min_std / (len(stds) - 1)
    min_std = min(stds)
    mean_at_min_std = means[index_min_std]

    axs[1].annotate('min std', xy=(index_min_std, min_std + 0.0003), xytext=(-25, 25), textcoords='offset points',
                    arrowprops=dict(arrowstyle="-|>"))
    axs[0].annotate('', xy=(index_min_std, mean_at_min_std + 0.0005), xytext=(0, 25), textcoords='offset points',
                    arrowprops=dict(arrowstyle="-|>"))

    # plt.text(20, 2.5, rf'Distance mean', {'color': 'black', 'fontsize': 20})

    fig.savefig(filepath, dpi=300)
    print(f'Plot saved as {filepath}')
    return optimal_flag_phase_in_rad, mean_at_min_std


def plot_spatiotemporal_variation(dataset, spatial_cvs, temporal_cvs, sizes=None,
                                  save_to=None, save_as=f'velocity_flag.{suf}'):
    d = dataset
    Nvels = len(spatial_cvs)
    N_svels = int(Nvels / 2)
    N_lvels = int(Nvels / 2) - 1
    if save_to is None:
        save_to = d.plot_dir
    if not os.path.exists(save_to):
        os.makedirs(save_to)
    filepath = os.path.join(save_to, save_as)
    fig, ax = plt.subplots(1,1, figsize=(15, 15))
    # r'$\Theta_{bend}$'
    c = 'c'
    svel_num_strings = ['{' + str(i + 1) + '}' for i in range(N_svels)]
    lvel_num_strings = ['{' + str(i + 2) + '}' for i in range(N_lvels)]
    labels = [r'$v_{cen}$'] + \
             [rf'$v^{c}_{i}$' for i in lvel_num_strings] + [rf'$v_{i}$' for i in svel_num_strings]
    markers = ['s'] + ['o' for i in range(N_lvels)] + ['v' for i in range(N_svels)]
    cnum = 1 + N_svels
    cmap = plt.get_cmap('hsv')
    cmap = [cmap(1. * i / cnum) for i in range(cnum)]
    cmap = [cmap[0]] + cmap[2:] + cmap[1:]
    if sizes is None:
        for v, m, scv, tcv, c in zip(labels, markers, spatial_cvs, temporal_cvs, cmap):
            plt.scatter(scv, tcv, marker=m, c=c, label=v)
    else:
        for v, m, scv, tcv, c, s in zip(labels, markers, spatial_cvs, temporal_cvs, cmap, sizes):
            plt.scatter(scv, tcv, marker=m, c=c, label=v, s=s)
    plt.legend(loc='upper left', ncol=2, handleheight=2.4, labelspacing=0.05)
    # ax.legend(loc='upper left', fontsize=15, bbox_to_anchor=(1.03, 1))
    plt.ylabel(r'$\overline{cv}_{temporal}$')
    plt.xlabel(r'$\overline{cv}_{spatial}$')
    plt.tight_layout()
    fig.savefig(filepath, dpi=300)
    print(f'Image saved as {filepath}')


def plot_distance_to_source(dataset, experiment):
    d = dataset
    s = d.step_data
    save_to = os.path.join(d.plot_dir, 'distance2source_timeplots')

    figsize = (10, 5)
    l_dst = 'distance $(mm)$'
    l_sc_dst = 'scal distance $(-)$'
    l_time = 'time $(sec)$'

    Nquantiles = 3

    if experiment == 'chemorbit':
        y = 20
        d.plot_step_data(parameters=['dst_to_center'], title=' ', mode='time',
                         figsize=figsize, plot_quantiles=Nquantiles,
                         xlim=[0, 600], ylim=[0, y], xlabel=l_time, ylabel=l_dst,
                         save_to=save_to, save_as=f'dst_to_source_timeplot.{suf}')

        y = 5
        d.plot_step_data(parameters=['scaled_dst_to_center'], title=' ', mode='time',
                         figsize=figsize, plot_quantiles=Nquantiles,
                         xlim=[0, 600], ylim=[0, y], xlabel=l_time, ylabel=l_sc_dst,
                         save_to=save_to, save_as=f'scaled_dst_to_source_timeplot.{suf}')

    elif experiment == 'chemotax':
        y = 450
        d.plot_step_data(parameters=['dst_to_chemotax_odor'], title=' ', mode='time',
                         figsize=figsize, plot_quantiles=Nquantiles,
                         xlim=[0, 180], ylim=[0, y], xlabel=l_time, ylabel=l_dst,
                         save_to=save_to, save_as=f'dst_to_source_timeplot.{suf}')

        y = 120
        d.plot_step_data(parameters=['scaled_dst_to_chemotax_odor'], title=' ', mode='time',
                         figsize=figsize, plot_quantiles=Nquantiles,
                         xlim=[0, 180], ylim=[0, y], xlabel=l_time, ylabel=l_sc_dst,
                         save_to=save_to, save_as=f'scaled_dst_to_source_timeplot.{suf}')


def plot_olfaction(dataset):
    d = dataset
    s = d.step_data
    save_to = os.path.join(d.plot_dir, 'olfaction_timeplots')
    figsize = (30, 5)
    l_dst = 'distance $(mm)$'
    l_sc_dst = 'scal distance $(-)$'
    l_time = 'time $(sec)$'
    xlim = [40, 60]
    ylim_concentration = [0.0, 1.5]
    y = 15
    d.plot_step_data(parameters=['first_odor_concentration', 'olfactory_activation'],
                     title='concentration to olfaction', mode='time',
                     figsize=figsize,
                     xlim=xlim,  # ylim=ylim_concentration,
                     xlabel=l_time,  # ylabel=l_sc_dst,
                     save_to=save_to, save_as=f'concentration_to_olfaction.{suf}')

    d.plot_step_data(parameters=['olfactory_activation', 'turner_activity'], title='olfaction to turner_activity',
                     mode='time',
                     figsize=figsize,
                     xlim=xlim,  # ylim=ylim_concentration,
                     xlabel=l_time,  # ylabel=l_sc_dst,
                     save_to=save_to, save_as=f'olfaction_to_turner_activity.{suf}')

    d.plot_step_data(parameters=['olfactory_activation', 'turner_activation'], title='olfaction to turner', mode='time',
                     figsize=figsize,
                     xlim=xlim,  # ylim=[0, y],
                     xlabel=l_time,  # ylabel=l_sc_dst,
                     save_to=save_to, save_as=f'olfaction_to_turner.{suf}')

    d.plot_step_data(parameters=['olfactory_activation', 'torque'], title='olfaction to torque', mode='time',
                     figsize=figsize,
                     xlim=xlim,  # ylim=[0, y],
                     xlabel=l_time,  # ylabel=l_sc_dst,
                     save_to=save_to, save_as=f'olfaction_to_torque.{suf}')

    d.plot_step_data(parameters=['first_odor_concentration', 'orientation_to_center'],
                     title='concentration to orientation', mode='time',
                     figsize=figsize,
                     xlim=xlim,  # ylim=ylim_concentration,
                     xlabel=l_time,  # ylabel=l_sc_dst,
                     save_to=save_to, save_as=f'concentration_to_orientation.{suf}')

    d.plot_step_data(parameters=['orientation_to_center', 'olfactory_activation'], title='orientation to olfaction',
                     mode='time',
                     figsize=figsize,
                     xlim=xlim,  # ylim=[0, y],
                     xlabel=l_time,  # ylabel=l_sc_dst,
                     save_to=save_to, save_as=f'orientation_to_olfaction.{suf}')

    d.plot_step_data(parameters=['first_odor_concentration', 'turner_activity'],
                     title='concentration to turner_activity', mode='time',
                     figsize=figsize,
                     xlim=xlim,  # ylim=[0, y],
                     xlabel=l_time,  # ylabel=l_sc_dst,
                     save_to=save_to, save_as=f'concentration_to_turner_activity.{suf}')


def plot_2D_countour(x, y, z, dimensions, Cmax, filepath):
    xmin, xmax = dimensions[0]
    ymin, ymax = dimensions[1]
    # define grid.
    xi = np.linspace(xmin, xmax, 1000)
    yi = np.linspace(ymin, ymax, 1000)
    ## grid the data.
    zi = griddata((x, y), z, (xi[None, :], yi[:, None]), method='cubic')
    levels = np.linspace(0.0, Cmax, 10000)
    fig = plt.figure(figsize=(xmax - xmin, ymax - ymin))
    # ax = plt.gca()
    # ax.axes.xaxis.set_visible(False)
    # ax.axes.yaxis.set_visible(False)
    # contour the gridded data, plotting dots at the randomly spaced data points.
    CS = plt.contour(xi, yi, zi, len(levels), linewidths=0.0, colors='k', levels=levels)
    # CS = plt.contourf(xi,yi,zi,15,cmap=plt.cm.jet)
    CS = plt.contourf(xi, yi, zi, len(levels), cmap=cm.Purples, levels=levels, alpha=0.9)
    # cbaxes = fig.add_axes([0.15, 0.8, 2.0, 0.2])
    cbaxes = fig.add_axes([0.68, 0.93, 2.0, 0.2])
    cbar = fig.colorbar(CS, cax=cbaxes, orientation="horizontal", ticks=[0, Cmax])
    # cbar.set_ticks([0.18, 0.9, 0.97])
    # cbar = fig.colorbar(CS, cax=cbaxes, orientation="horizontal", ticks=[0, Cmax/2, Cmax])
    cbar.ax.set_xticklabels([0, f'${int(Cmax)} \mu$M'])

    # cbar.ax.set_xticklabels(['$0 \mu$M', f'${int(Cmax/2)} \mu$M', f'${int(Cmax)} \mu$M'])

    plt.xlim(xmin, xmax)
    plt.ylim(ymin, ymax)
    # plt.tick_params(
    #     axis='both',  # changes apply to the x-axis
    #     which='both',  # both major and minor ticks are affected
    #     bottom=False,  # ticks along the bottom edge are off
    #     top=False,  # ticks along the top edge are off
    #     labelbottom=False)  # labels along the bottom edge are off
    plt.locator_params(nbins=4)
    fig.savefig(filepath, dpi=300)
    print(f'Image saved as {filepath}')


def gauss(x, y, Sigma, mu):
    X = np.vstack((x, y)).T
    mat_multi = np.dot((X - mu[None, ...]).dot(np.linalg.inv(Sigma)), (X - mu[None, ...]).T)
    return np.diag(np.exp(-1 * (mat_multi)))


def plot_2D_odorscape(dimensions, Cmax, Cstd, filepath, pos=None):
    if pos is None:
        pos = [0., 0.]
    npts = 10000
    x = np.random.uniform(dimensions[0][0], dimensions[0][1], npts)
    y = np.random.uniform(dimensions[1][0], dimensions[1][1], npts)
    z = gauss(x, y, Sigma=np.asarray([[Cstd, 0.0], [0.0, Cstd]]), mu=np.asarray(pos)) * Cmax
    plot_2D_countour(x, y, z, dimensions=dimensions, Cmax=Cmax, filepath=filepath)


def plot_bend_change_over_displacement(dataset, return_fig=False):
    s = dataset.step_data
    save_to = os.path.join(dataset.plot_dir, 'plot_bend_change_over_displacement')
    if not os.path.exists(save_to):
        os.makedirs(save_to)
    figsize = (5, 5)

    b, o = 'bend', nam.unwrap('front_orientation')
    bv, ov = nam.vel(b), nam.vel('front_orientation')
    sd = nam.scal(dataset.distance)

    ind = s[sd].dropna().index
    b_data = s.loc[ind, b].values
    bv_data = s.loc[ind, bv].values
    ov_data = s.loc[ind, ov].values
    sd_data = s.loc[ind, sd].values

    bv_correction = bv_data / dataset.fr * np.sign(b_data)

    # xlim=ylim=[-180,180]

    fig, ax = plt.subplots(1, 1, figsize=figsize)
    ax.scatter(x=sd_data, y=bv_correction, marker='.')
    # ax.set_xlim(xlim)
    # ax.set_ylim(ylim)
    filename = f'bend_change_over_displacement.{suf}'
    return process_plot(fig, save_to, filename, return_fig)


def plot_stride_Dbend(datasets, labels, show_text=False, save_to=None, return_fig=False):
    Ndatasets, colors, save_to = plot_config(datasets, labels, save_to, subfolder='stride')
    filename = f'stride_bend_change.{suf}'

    p = 'bend'
    b0_par = f'{p}_at_stride_start'
    b1_par = f'{p}_at_stride_stop'

    b0s = []
    b1s = []
    dbs = []
    for d in datasets:
        b0 = d.get_par(b0_par).dropna().values.flatten()
        b1 = d.get_par(b1_par).dropna().values.flatten()
        sign_b = np.sign(b0)
        b0 *= sign_b
        b1 *= sign_b
        db = b1 - b0
        b0s.append(b0)
        b1s.append(b1)
        dbs.append(db)

    figsize = (5, 5)

    ylim = [-60, 60]
    xlim = [0, 85]

    fig, ax = plt.subplots(1, 1, figsize=figsize)
    ax.yaxis.set_major_locator(ticker.MaxNLocator(5))
    fits = {}
    for i, (b0, b1, db, label, c) in enumerate(zip(b0s, b1s, dbs, labels, colors)):
        b0 = b0[:500]
        db = db[:500]
        ax.scatter(x=b0, y=db, marker='o', s=2.0, alpha=0.6, color=c, label=label)
        ax.set_xlim(xlim)
        ax.set_ylim(ylim)
        # ax.set_xlabel('bend at stride start, deg')
        ax.set_xlabel(r'$\theta_{bend}$ at stride start $(deg)$')
        # ax.set_ylabel('bend change over stride, deg')
        ax.set_ylabel(r'$\Delta\theta_{bend}$ over stride $(deg)$')

        m, k = np.polyfit(b0, db, 1)
        m = np.round(m, 2)
        k = np.round(k, 2)
        fits[label] = [m, k]
        ax.plot(b0, m * b0 + k, linewidth=4, color=c)
        if show_text and i == 0:
            ax.text(80, 50, rf'$\Delta\theta_{{b}}={m} \theta_{{b}}$', fontsize=15)
            # ax.text(80, 50, rf'$\Delta\theta_{{b}}={m}*\theta_{{b}} + {k}$', fontsize=15)
        print(f'Bend correction during strides for {label} fitted as : db={m}*b + {k}')
    plt.subplots_adjust(bottom=0.15, top=0.95, left=0.2, right=0.99, wspace=0.01)
    return process_plot(fig, save_to, filename, return_fig)


def plot_stride_Dorient(datasets, labels, simVSexp=False, absolute=True, save_to=None, legend=False, return_fig=False):
    Ndatasets, colors, save_to = plot_config(datasets, labels, save_to, subfolder='stride')
    filename = f'stride_orient_change.{suf}'

    par_shorts = ['str_fo', 'str_ro']
    pars, sim_labels, exp_labels, xlabels = [
        par_db[['par', 'symbol', 'exp_symbol', 'unit']].loc[par_shorts].values[:, k].tolist() for k in range(4)]
    ranges = [80, 80]

    if simVSexp:
        p_labels = [[sl, el] for sl, el in zip(sim_labels, exp_labels)]
    else:
        p_labels = [[sl] * Ndatasets for sl in sim_labels]

    fig, axs = plt.subplots(1, len(pars), figsize=(10, 5), sharey=True)
    if len(pars) > 1:
        axs = axs.ravel()
    else:
        axs = [axs]
    nbins = 200

    for i, (p, r, p_lab, xlab) in enumerate(zip(pars, ranges, p_labels, xlabels)):
        for j, d in enumerate(datasets):
            v = d.get_par(p).dropna().values
            if absolute:
                v = np.abs(v)
                r1, r2 = 0, r
            else:
                r1, r2 = -r, r
            x = np.linspace(r1, r2, nbins)
            weights = np.ones_like(v) / float(len(v))
            axs[i].hist(v, color=colors[j], bins=x, label=p_lab[j],
                        weights=weights, alpha=0.5)
        axs[i].set_xlabel(xlab)
        axs[i].yaxis.set_major_locator(ticker.MaxNLocator(4))
        if legend:
            axs[i].legend()
    axs[0].set_ylabel('probability')
    plt.subplots_adjust(bottom=0.15, top=0.95, left=0.1, right=0.99, wspace=0.01)
    return process_plot(fig, save_to, filename, return_fig)


def plot_interference(datasets, labels, mode='orientation', agent_idx=None,
                      include_rear=True, save_to=None, save_as=None, return_fig=False):
    Ndatasets, colors, save_to = plot_config(datasets, labels, save_to, subfolder='interference')
    if save_as is None:
        if agent_idx is None:
            save_as = f'interference_{mode}.{suf}'
        else:
            save_as = f'interference_{mode}_agent_idx_{agent_idx}.{suf}'

    # if agent_id is not None and N != 1:
    #     raise ValueError('Individual larva data can be plotted only when a single dataset is provided.')

    par_shorts = ['sv']
    if mode == 'orientation':
        par_shorts.append('fov')
    elif mode == 'orientation_x2':
        par_shorts.append('fov')
        par_shorts.append('rov')
    elif mode == 'bend':
        par_shorts.append('bv')
    elif mode == 'spinelength':
        par_shorts.append('l')

    pars, sim_labels, exp_labels, units = [
        par_db[['par', 'symbol', 'exp_symbol', 'unit']].loc[par_shorts].values[:, k].tolist() for k in range(4)]
    # print(pars, sim_labels, exp_labels, units)
    fig, axs = plt.subplots(len(pars), 1, figsize=(10, len(pars) * 5), sharex=True)
    axs = axs.ravel()

    if mode in ['bend', 'orientation']:
        ang_ylim = [0, 60]
    elif mode in ['spinelength']:
        ang_ylim = None

    if agent_idx is not None:
        data = [[d.load_chunk_dataset(chunk='stride', parameter=p).loc[d.agent_ids[agent_idx]].values for p in pars] for
                d in datasets]
    else:
        data = [[d.load_chunk_dataset(chunk='stride', parameter=p).values for p in pars] for d in datasets]
    Npoints = data[0][0].shape[1]
    for d0, c, color, label in zip(data, colors, colors, labels):
        if mode in ['bend', 'orientation']:
            d0 = [np.abs(d) for d in d0]
        for i, (p, pd) in enumerate(zip(pars, d0)):
            ts_m, ts_l, ts_h = np.nanquantile(pd, q=0.5, axis=0), \
                               np.nanquantile(pd, q=0.25, axis=0), \
                               np.nanquantile(pd, q=0.75, axis=0)
            plot_mean_and_range(x=np.arange(len(ts_m)), mean=ts_m, lb=ts_l, ub=ts_h, axis=axs[i],
                                color_mean=c, color_shading=color, label=label)
            axs[i].yaxis.set_major_locator(ticker.MaxNLocator(4))
            axs[i].set_ylim(ymin=0)
    Nticks = 5
    ticks = np.linspace(0, Npoints - 1, Nticks)
    axs[-1].set_xticks(ticks=ticks)
    axs[-1].set_xticklabels(labels=[r'$0$', r'$\frac{\pi}{2}$', r'$\pi$', r'$\frac{3\pi}{2}$', r'$2\pi$'])
    axs[-1].set_xlim([0, Npoints - 1])
    axs[-1].set_ylim(ymin=0)
    axs[-1].set_xlabel('$\phi_{stride}$')

    for j in range(len(pars)):
        axs[j].legend(loc='upper right')
        axs[j].set_ylabel(units[j])
        if j != 0:
            axs[j].set_ylim(ang_ylim)
    fig.subplots_adjust(top=0.97, bottom=0.2 / len(pars), left=0.12, right=0.95, hspace=.1, wspace=0.05)
    return process_plot(fig, save_to, save_as, return_fig)


def plot_dispersion(datasets, labels, ranges=[[0, 40]], scaled=False, save_to=None, fig_cols=1, return_fig=False):
    Ndatasets, colors, save_to = plot_config(datasets, labels, save_to, subfolder='dispersion')
    for r in ranges:
        r0, r1, dur = r[0], r[1], r[1] - r[0]
        t0, t1 = int(r0 * datasets[0].fr), int(r1 * datasets[0].fr)
        if r0 == 0:
            par = f'dispersion'
        else:
            par = f'dispersion_{r0}'
        if scaled:
            filename = f'scaled_dispersion_{r0}-{r1}_{fig_cols}.{suf}'
            ylab = 'scaled dispersion'
        else:
            filename = f'dispersion_{r0}-{r1}_{fig_cols}.{suf}'
            ylab = r'dispersion $(mm)$'
        Nticks = t1 - t0
        trange = np.linspace(r0, r1, Nticks)
        fig, axs = plt.subplots(1, 1, figsize=(5 * fig_cols, 5))
        for d, lab, c in zip(datasets, labels, colors):
            dsp_df = d.load_dispersion_dataset(par=par, scaled=scaled)
            dsp_m = dsp_df['median']
            dsp_u = dsp_df['upper']
            dsp_b = dsp_df['lower']

            dsp_m = dsp_m[t0:t1]
            dsp_u = dsp_u[t0:t1]
            dsp_b = dsp_b[t0:t1]
            plot_mean_and_range(x=trange, mean=dsp_m, lb=dsp_b, ub=dsp_u, axis=axs, color_mean=c,
                                color_shading=c, label=lab)
        axs.set_ylabel(ylab)
        axs.set_xlabel('time, $sec$')
        axs.set_xlim([trange[0], trange[-1]])
        axs.yaxis.set_major_locator(ticker.MaxNLocator(4))
        axs.xaxis.set_major_locator(ticker.MaxNLocator(4))
        axs.legend(loc='upper left')
        fig.subplots_adjust(top=0.95, bottom=0.15, left=0.2 / fig_cols, right=0.95, hspace=.005, wspace=0.05)
        return process_plot(fig, save_to, filename, return_fig)


def plot_pathlength(datasets, labels, scaled=True, save_to=None, save_as=None, return_fig=False):
    Ndatasets, colors, save_to = plot_config(datasets, labels, save_to)
    Nticks = len(datasets[0].step_data.index.unique('Step'))
    t0, t1 = 0, int(Nticks / datasets[0].fr / 60)

    lab = 'pathlength'
    if scaled:
        filename = f'scaled_{lab}.{suf}'
        ylab = f'scaled {lab} $(-)$'
    else:
        filename = f'{lab}.{suf}'
        ylab = f'{lab} $(mm)$'

    if save_as is not None:
        filename = save_as

    trange = np.linspace(t0, t1, Nticks)
    fig, axs = plt.subplots(1, 1, figsize=(10, 5))
    for d, lab, c in zip(datasets, labels, colors):
        dst_df = d.step_data['cum_dst']
        dst_m = dst_df.groupby(level='Step').quantile(q=0.5)
        dst_u = dst_df.groupby(level='Step').quantile(q=0.75)
        dst_b = dst_df.groupby(level='Step').quantile(q=0.25)
        plot_mean_and_range(x=trange, mean=dst_m, lb=dst_b, ub=dst_u, axis=axs, color_mean=c,
                            color_shading=c, label=lab)
    axs.set_ylabel(ylab)
    axs.set_xlabel('time, $min$')
    axs.set_xlim([trange[0], trange[-1]])
    axs.xaxis.set_major_locator(ticker.MaxNLocator(5))
    axs.legend(loc='upper left', fontsize=9)
    fig.subplots_adjust(top=0.95, bottom=0.15, left=0.1, right=0.95, hspace=.005, wspace=0.05)
    return process_plot(fig, save_to, filename, return_fig)


def plot_gut(datasets, labels, save_to=None, save_as=None, return_fig=False):
    Ndatasets, colors, save_to = plot_config(datasets, labels, save_to)
    Nticks = len(datasets[0].step_data.index.unique('Step'))
    t0, t1 = 0, int(Nticks / datasets[0].fr / 60)

    lab = 'gut'

    filename = f'{lab}.{suf}'
    ylab = f'% {lab} occupied'

    if save_as is not None:
        filename = save_as

    trange = np.linspace(t0, t1, Nticks)
    fig, axs = plt.subplots(1, 1, figsize=(10, 5))
    for d, lab, c in zip(datasets, labels, colors):
        dst_df = d.step_data['filled_gut_ratio'] * 100
        dst_m = dst_df.groupby(level='Step').quantile(q=0.5)
        dst_u = dst_df.groupby(level='Step').quantile(q=0.75)
        dst_b = dst_df.groupby(level='Step').quantile(q=0.25)
        plot_mean_and_range(x=trange, mean=dst_m, lb=dst_b, ub=dst_u, axis=axs, color_mean=c,
                            color_shading=c, label=lab)
    axs.set_ylabel(ylab)
    axs.set_xlabel('time, $min$')
    axs.set_xlim([trange[0], trange[-1]])
    axs.set_ylim([0, 100])
    axs.xaxis.set_major_locator(ticker.MaxNLocator(5))
    axs.yaxis.set_major_locator(ticker.MaxNLocator(5))
    axs.legend(loc='upper left', fontsize=9)
    fig.subplots_adjust(top=0.95, bottom=0.15, left=0.1, right=0.95, hspace=.005, wspace=0.05)
    return process_plot(fig, save_to, filename, return_fig)


def plot_food_amount(datasets, labels, save_to=None, save_as=None, filt_amount=False, scaled=False, return_fig=False):
    Ndatasets, colors, save_to = plot_config(datasets, labels, save_to)
    Nticks = len(datasets[0].step_data.index.unique('Step'))
    t0, t1 = 0, int(Nticks / datasets[0].fr / 60)

    filename = f'food_intake.{suf}'
    ylab = r'Cumulative food intake $(mg)$'
    par = 'amount_eaten'
    if scaled:
        filename = f'scaled_{filename}'
        ylab = r'Cumulative food intake as % larval mass'
        par = 'scaled_amount_eaten'
    if filt_amount:
        filename = f'filtered_{filename}'
        ylab = r'Food intake $(mg)$'
    if filt_amount and scaled:
        ylab = 'Food intake as % larval mass'

    if save_as is not None:
        filename = save_as

    trange = np.linspace(t0, t1, Nticks)
    fig, axs = plt.subplots(1, 1, figsize=(10, 5))
    for d, lab, c in zip(datasets, labels, colors):
        dst_df = d.step_data[par]

        dst_m = dst_df.groupby(level='Step').quantile(q=0.5)
        dst_u = dst_df.groupby(level='Step').quantile(q=0.75)
        dst_b = dst_df.groupby(level='Step').quantile(q=0.25)
        # print(dst_m)
        # print(type(dst_m))
        if filt_amount:
            sos = butter(N=1, Wn=0.1, btype='lowpass', analog=False, fs=Nticks / (t1 - t0), output='sos')
            dst_m = dst_m.diff()
            dst_m.iloc[0] = 0
            dst_m = sosfiltfilt(sos, dst_m)
            dst_u = dst_u.diff()
            dst_u.iloc[0] = 0
            dst_u = sosfiltfilt(sos, dst_u)
            dst_b = dst_b.diff()
            dst_b.iloc[0] = 0
            dst_b = sosfiltfilt(sos, dst_b)
            # print(dst_m)
            # print(type(dst_m))
            # for df in [dst_m, dst_u, dst_b] :
            #     df=df.diff()
            #     df.iloc[0]=0
            #     df = sosfiltfilt(sos, df)
        plot_mean_and_range(x=trange, mean=dst_m, lb=dst_b, ub=dst_u, axis=axs, color_mean=c,
                            color_shading=c, label=lab)
    axs.set_ylabel(ylab)
    axs.set_xlabel('time, $min$')
    axs.set_xlim([trange[0], trange[-1]])
    axs.xaxis.set_major_locator(ticker.MaxNLocator(5))
    axs.legend(loc='upper left', fontsize=9)
    fig.subplots_adjust(top=0.95, bottom=0.15, left=0.1, right=0.95, hspace=.005, wspace=0.05)
    return process_plot(fig, save_to, filename, return_fig)


def plot_heatmap_PI(csv_filepath='PIs.csv', heatmap_filepath='PI_heatmap.pdf', return_fig=False):
    print('Creating heatmap')
    new_data = pd.read_csv(csv_filepath, index_col=0)
    gains = new_data.index.values
    Ngains = len(gains)
    # print(new_data.index.values)
    # del new_data.index.name
    grid_kws = {"height_ratios": (.9, .05), "hspace": 0.4}
    fig, ax = plt.subplots(figsize=(6, 5))
    sns.heatmap(new_data, annot=False, fmt="g", cmap='RdYlGn', vmin=-1, vmax=1, ax=ax,
                cbar_kws={"orientation": "vertical",
                          'label': 'Preference Index for left odor',
                          'ticks': [1, 0, -1]})
    # ax.set_size_cm(3.5, 3.5)
    cax = plt.gcf().axes[-1]
    cax.tick_params(length=0)

    # ax.set_title('Preference index for variable odor gain combinations')
    ax.set_yticklabels(ax.get_yticklabels(), rotation=0)
    ax.set_xlabel(r'Left odor gain, $G_{L}$')
    ax.set_ylabel(r'Right odor gain, $G_{R}$')
    # ax.set_ylabel(r'$V_{left}$')
    # ax.set_ylabel(r'Valence$_{left}$')
    # ax.set_ylabel('Left odor valence')
    # ax.set_xlabel(r'$Gain_{right}$')
    # ax.set_xlabel(r'$V_{right}$')
    # ax.set_xlabel(r'Valence$_{right}$')
    # ax.set_xlabel('Right odor valence')
    ax.xaxis.set_ticks_position('top')
    r = np.linspace(0.5, Ngains - 0.5, 5)
    ax.set_xticks(r)
    ax.set_yticks(r)
    ax.set_xticklabels(gains[r.astype(int)])
    ax.set_yticklabels(gains[r.astype(int)])
    plt.subplots_adjust(left=0.15, right=0.95, bottom=0.15)
    plt.savefig(heatmap_filepath, dpi=300)
    print(f'Heatmap saved as {heatmap_filepath}')


def plot_odor_concentration(datasets, labels=None, save_to=None, return_fig=False):
    return plot_timeplot('c_odor1', datasets=datasets, labels=labels, save_to=save_to, return_fig=return_fig)

def plot_timeplot(par_short, datasets, labels=None, save_to=None, return_fig=False) :
    if par_short not in par_db.index.to_list() :
        raise ValueError (f'Parameter shortcut {par_short} does not exist in parameter database')
    par_dict=par_db.loc[par_short]
    par=par_dict['par']
    sim_label=par_dict['symbol']
    xlabel=par_dict['unit']

    d = datasets[0]
    s = d.step_data

    dc = s[par]
    dc0 = dc.xs(d.agent_ids[0], level='AgentID')

    dc_m = dc.groupby(level='Step').quantile(q=0.5)
    dc_u = dc.groupby(level='Step').quantile(q=0.75)
    dc_b = dc.groupby(level='Step').quantile(q=0.25)

    Nticks = len(dc_m)
    dur = int(Nticks / d.fr)
    trange = np.linspace(0, dur, Nticks)
    if save_to is None:
        save_to = d.plot_dir
    filename = f'{par}.{suf}'

    fig, axs = plt.subplots(1, 1, figsize=(7.5, 5))
    plot_mean_and_range(x=trange, mean=dc_m, lb=dc_u, ub=dc_b, axis=axs, color_mean='grey', color_shading='grey')
    axs.plot(trange, dc0, 'r')

    axs.set_ylabel(xlabel)
    axs.set_xlabel('time, $sec$')
    axs.set_xlim([trange[0], trange[-1]])
    # axs.legend(loc='upper right')
    axs.yaxis.set_major_locator(ticker.MaxNLocator(4))
    # axs[1].set_xticks([0.5, 1, 10])
    # axs[1].set_xticklabels(['0.5', '1', '10'])
    plt.subplots_adjust(bottom=0.15, left=0.15, right=0.95, top=0.95)
    return process_plot(fig, save_to, filename, return_fig)


def plot_stridesNpauses(datasets, labels, stridechain_duration=False, pause_chunk='pause', time_unit='sec',
                        plot_fits='all', range='broad', print_fits=False, only_fit_one=True, type='cdf',
                        save_to=None, save_as='stridesNpauses', save_fits_to=None, save_fits_as=None, return_fig=False):
    Ndatasets, colors, save_to = plot_config(datasets, labels, save_to, subfolder='bouts')
    if save_fits_to is None:
        save_fits_to = f'{save_to}/bout_fits'
    if not os.path.exists(save_fits_to):
        os.makedirs(save_fits_to)

    pause_discrete = False

    pause_lab = r'$\bf{pauses}$'
    chain_lab = r'$\bf{stridechains}$'

    pause_durs = []
    chain_durs = []

    frs = []
    for label, dataset in zip(labels, datasets):
        frs.append(dataset.fr)
        pause_par = nam.dur(pause_chunk)
        pause_dur = dataset.get_par(pause_par).dropna().values
        pause_min = 0.3
        pause_max = 12
        if time_unit == 'ms':
            pause_xlabel = 'time $(msec)$'
            pause_dur *= 1000
            pause_min *= 1000
            pause_max *= 1000
        elif time_unit == 'sec':
            pause_xlabel = 'time $(sec)$'
            pass

        if stridechain_duration:
            chain_par = nam.dur(nam.chain('stride'))
            chain_dur = dataset.get_par(chain_par).dropna().values
            chain_discrete = False
            chain_min = 0.5
            chain_max = 50
            if time_unit == 'ms':
                chain_xlabel = 'time $(msec)$'
                chain_dur *= 1000
                chain_min *= 1000
                chain_max *= 1000
            elif time_unit == 'sec':
                chain_xlabel = 'time $(sec)$'
                pass

        else:
            chain_par = nam.length(nam.chain('stride'))
            chain_dur = dataset.get_par(chain_par).dropna().values
            chain_xlabel = '# strides'
            chain_discrete = True
            chain_min = 1
            chain_max = 100
        pause_durs.append(pause_dur)
        chain_durs.append(chain_dur)

    min_pauses, max_pauses = [np.min(dur) for dur in pause_durs], [np.max(dur) for dur in pause_durs]
    min_chains, max_chains = [np.min(dur) for dur in chain_durs], [np.max(dur) for dur in chain_durs]

    if range == 'broad':
        pause_min, pause_max = np.min(min_pauses), np.max(max_pauses)
        chain_min, chain_max = np.min(min_chains), np.max(max_chains)
    elif range == 'restricted':
        pause_min, pause_max = np.max(min_pauses), np.min(max_pauses)
        chain_min, chain_max = np.max(min_chains), np.min(max_chains)
    elif range == 'default':
        pass

    ps = ['stride', 'pause']
    stored_pars = [
        [f'alpha_{p}', f'KS_pow_{p}', f'lambda_{p}', f'KS_exp_{p}', f'mu_log_{p}', f'sigma_log_{p}', f'KS_log_{p}'] for
        p in ps]
    fit_df = pd.DataFrame(index=labels, columns=flatten_list(stored_pars))
    fit_df['min_pause'] = np.clip(min_pauses, a_min=pause_min, a_max=+np.inf)
    fit_df['max_pause'] = np.clip(max_pauses, a_min=0, a_max=pause_max)
    fit_df['min_stride'] = np.clip(min_chains, a_min=chain_min, a_max=+np.inf)
    fit_df['max_stride'] = np.clip(max_chains, a_min=0, a_max=chain_max)

    # pause_min, pause_max = np.min(pause_dur), np.max(pause_dur)
    # chain_min, chain_max = np.min(chain_dur), np.max(chain_dur)

    for mode in ['pdf', 'cdf']:
        if type != mode:
            continue
        if not only_fit_one:
            j0 = 0
            filename = f'{save_as}_{mode}_{range}.{suf}'
        else:
            j0 = 1
            filename = f'{save_as}_{mode}_{range}_0.{suf}'
        fit_filename = f'bout_fits_{range}.csv'
        if save_fits_as is None:
            fit_filepath = os.path.join(save_fits_to, fit_filename)
        else:
            fit_filepath = save_fits_as

        fig, axs = plt.subplots(1, 2, figsize=(10, 5), sharex=False, sharey=True)
        axs = axs.ravel()

        for j, (pause_dur, chain_dur, c, label, fr) in enumerate(
                zip(pause_durs, chain_durs, colors, labels, frs)):

            for i, (dur, discrete, durmin, durmax) in enumerate(
                    zip([chain_dur, pause_dur],
                        [chain_discrete, pause_discrete], [chain_min, pause_min], [chain_max, pause_max])):
                # label = f'{label_prefix} {label_suffix}'
                # if use_min_values :
                #     durmax = np.max(dur)
                # else :
                #     durmin, durmax = np.min(dur), np.max(dur)
                dur = dur[dur >= durmin]
                dur = dur[dur <= durmax]

                u2, c2, c2cum = compute_density(dur, durmin, durmax, Nbins=64)
                du2 = 0.5 * (u2[:-1] + u2[1:])
                alpha = 1 + len(dur) / np.sum(np.log(dur / durmin))

                if discrete:
                    results = pow.Fit(dur, xmin=durmin, xmax=durmax, discrete=True)
                else:
                    results = pow.Fit(np.array(dur * fr).astype(int), xmin=int(durmin * fr), xmax=int(durmax * fr),
                                      discrete=True)
                alpha2 = results.power_law.alpha
                beta = len(dur) / np.sum(dur - durmin)
                mean_lognormal = np.mean(np.log(dur))
                std_lognormal = np.std(np.log(dur))

                KS_plaw = np.max(np.abs(c2cum - 1 + powerlaw_cdf(u2, durmin, alpha)))
                KS_exp = np.max(np.abs(c2cum - 1 + exponential_cdf(u2, durmin, beta)))
                KS_logn = np.max(np.abs(c2cum - 1 + lognormal_cdf(u2, mean_lognormal, std_lognormal)))

                if print_fits:
                    print()
                    if i == 0:
                        print(f'-----{label}-stridechains----------')
                    else:
                        print(f'-----{label}-pauses----------')
                    print(f'range : {np.min(dur)} - {np.max(dur)}, Nbouts : {len(dur)}')
                    print("powerlaw exponent MLE:", alpha)
                    print("powerlaw exponent powerlaw package:", alpha2)
                    print("exponential exponent MLE:", beta)
                    print("lognormal mean,std:", mean_lognormal, std_lognormal)
                    print('KS plaw', KS_plaw)
                    print('KS exp', KS_exp)
                    print('KS logn', KS_logn)
                    print()

                to_store = np.round([alpha, KS_plaw, beta, KS_exp, mean_lognormal, std_lognormal, KS_logn], 3)
                fit_df.loc[label, stored_pars[i]] = to_store

                idx_max = np.argmin([KS_plaw, KS_exp, KS_logn])
                lws = [2, 2, 2]
                lws[idx_max] = 4

                if mode == 'cdf':
                    ylabel = 'cumulative probability'
                    if Ndatasets > 1:
                        axs[i].loglog(u2, c2cum, '.', color=c, alpha=0.7)
                        # axs[i].loglog(u2, c2cum, '.', color=c, label=label, alpha=0.7)
                    else:
                        axs[i].loglog(u2, c2cum, '.', color=c, alpha=0.7)
                    if plot_fits == 'all':
                        if j == j0:
                            axs[i].loglog(u2, 1 - powerlaw_cdf(u2, durmin, alpha), 'c', lw=lws[0], label='powerlaw')
                            axs[i].loglog(u2, 1 - exponential_cdf(u2, durmin, beta), 'g', lw=lws[1],
                                          label='exponential')
                            axs[i].loglog(u2, 1 - lognormal_cdf(u2, mean_lognormal, std_lognormal), 'm', lw=lws[2],
                                          label='lognormal')
                        else:
                            if not only_fit_one:
                                axs[i].loglog(u2, 1 - powerlaw_cdf(u2, durmin, alpha), 'c', lw=lws[0])
                                axs[i].loglog(u2, 1 - exponential_cdf(u2, durmin, beta), 'g', lw=lws[1])
                                axs[i].loglog(u2, 1 - lognormal_cdf(u2, mean_lognormal, std_lognormal), 'm', lw=lws[2])
                    elif plot_fits == 'best':
                        if idx_max == 0:
                            axs[i].loglog(u2, 1 - powerlaw_cdf(u2, durmin, alpha), color=c, lw=lws[0])
                        elif idx_max == 1:
                            axs[i].loglog(u2, 1 - exponential_cdf(u2, durmin, beta), color=c, lw=lws[1])
                        elif idx_max == 2:
                            axs[i].loglog(u2, 1 - lognormal_cdf(u2, mean_lognormal, std_lognormal), color=c, lw=lws[2])
                    axs[i].axis([durmin, 1.1 * durmax, 1E-4, 1.1 * 1E-0])
                elif mode == 'pdf':
                    ylabel = 'probability'
                    if Ndatasets > 1:
                        axs[i].loglog(du2, c2, '.', color=c, alpha=0.7)
                        # axs[i].loglog(du2, c2, '.', color=c, label=label, alpha=0.7)
                    else:
                        axs[i].loglog(du2, c2, '.', color=c, alpha=0.7)
                    if plot_fits == 'all':
                        if j == j0:
                            axs[i].loglog(du2, powerlaw_pdf(du2, durmin, alpha), 'c', lw=lws[0], label='powerlaw')
                            axs[i].loglog(du2, exponential_pdf(du2, durmin, beta), 'g', lw=lws[1],
                                          label='exponential')
                            axs[i].loglog(du2, lognormal_pdf(du2, mean_lognormal, std_lognormal), 'm', lw=lws[2],
                                          label='lognormal')
                        else:
                            if not only_fit_one:
                                axs[i].loglog(du2, powerlaw_pdf(du2, durmin, alpha), 'c', lw=lws[0])
                                axs[i].loglog(du2, exponential_pdf(du2, durmin, beta), 'g', lw=lws[1])
                                axs[i].loglog(du2, lognormal_pdf(du2, mean_lognormal, std_lognormal), 'm', lw=lws[2])
                    elif plot_fits == 'best':
                        if idx_max == 0:
                            axs[i].loglog(du2, powerlaw_pdf(du2, durmin, alpha), color=c, lw=lws[0])
                        elif idx_max == 1:
                            axs[i].loglog(du2, exponential_pdf(du2, durmin, beta), color=c, lw=lws[1])
                        elif idx_max == 2:
                            axs[i].loglog(du2, lognormal_pdf(du2, mean_lognormal, std_lognormal), color=c, lw=lws[2])
                    axs[i].axis([durmin, 1.1 * durmax, 1E-6, 1.1 * 1E-0])
                axs[i].legend(loc='lower left', fontsize=15)
        # axs[0].yaxis.set_major_locator(ticker.MaxNLocator(4))
        axs[0].set_ylabel(ylabel)
        axs[0].set_xlabel(chain_xlabel)
        axs[1].set_xlabel(pause_xlabel)
        axs[0].set_title(chain_lab)
        axs[1].set_title(pause_lab)
        fig.subplots_adjust(top=0.92, bottom=0.15, left=0.15, right=0.95, hspace=.005, wspace=0.05)
        fit_df.to_csv(fit_filepath, index=True, header=True)
        print(f'Fits saved as {fit_filename}.')
        return process_plot(fig, save_to, filename, return_fig)


def plot_vel_during_strides(dataset, use_component=False, save_to=None, return_fig=False):
    chunk = 'stride'
    Npoints = 64
    d = dataset
    s = d.step_data

    if save_to is None:
        save_to = os.path.join(d.plot_dir, 'plot_vel_during_strides')
    if not os.path.exists(save_to):
        os.makedirs(save_to)
    save_as_lin = f'linear_velocities_during_strides.{suf}'
    save_as_ang = f'angular_velocity_during_strides.{suf}'
    filepath_lin = os.path.join(save_to, save_as_lin)
    filepath_ang = os.path.join(save_to, save_as_ang)
    filepaths = [filepath_lin, filepath_ang]

    point = d.point
    svels = nam.scal(nam.vel(d.points))
    lvels = nam.scal(nam.lin(nam.vel(d.points[1:])))
    ids = d.agent_ids
    hov = nam.vel('front_orientation')

    if use_component:
        lin_vels = lvels
    else:
        lin_vels = svels
    lin_vels = [lin_vels[0], lin_vels[int(len(lin_vels) / 2)], lin_vels[-1]]
    ang_vels = [hov]
    vels = [lin_vels, ang_vels]
    vels_list = lin_vels + ang_vels
    Nvels = len(vels_list)

    all_agents = [s.xs(id, level='AgentID', drop_level=True) for id in ids]
    all_flag_starts = [ag[ag[nam.start(chunk)] == True].index.values.astype(int) for ag in all_agents]
    all_flag_stops = [ag[ag[nam.stop(chunk)] == True].index.values.astype(int) for ag in all_agents]

    all_vel_timeseries = [[] for i in range(Nvels)]
    for agent_id, flag_starts, flag_stops in zip(ids, all_flag_starts, all_flag_stops):
        for start, stop in zip(flag_starts, flag_stops):
            for i, vel in enumerate(vels_list):
                vel_timeserie = s.loc[(slice(start, stop), agent_id), vel].values
                all_vel_timeseries[i].append(vel_timeserie)

    durations = [len(i) for i in all_vel_timeseries[0]]

    lin_vel_timeseries = all_vel_timeseries[:-1]
    ang_vel_timeseries = [[np.abs(a) for a in all_vel_timeseries[-1]]]
    vel_timeseries = [lin_vel_timeseries, ang_vel_timeseries]

    lin_cs = ['black', 'seagreen', 'mediumturquoise']
    # lin_cs = ['darkred', 'red', 'lightsalmon']
    ang_cs = ['black']
    cs = [lin_cs, ang_cs]
    lin_labels = [r'$\bf{head}$', r'$\bf{midpoint}$', r'$\bf{tail}$']
    ang_labels = [r'$\dot{\theta}_{or}$']
    labels = [lin_labels, ang_labels]
    ylabels = ['scal linear velocity', 'angular velocity $(deg/sec)$']

    for i in [0, 1]:
        fig, ax = plt.subplots(1, 1, figsize=(10, 5))
        # print(vels[i], cs[i], cs[i], labels[i])
        for serie, vel, col, c, l in zip(vel_timeseries[i], vels[i], cs[i], cs[i], labels[i]):
            print(vel, col, c, l)
            array = [np.interp(x=np.linspace(0, 2 * np.pi, Npoints), xp=np.linspace(0, 2 * np.pi, dur), fp=ts, left=0,
                               right=0) for dur, ts in zip(durations, serie)]
            serie_m, serie_l, serie_h = np.nanquantile(array, q=0.5, axis=0), \
                                        np.nanquantile(array, q=0.25, axis=0), \
                                        np.nanquantile(array, q=0.75, axis=0)

            plot_mean_and_range(x=np.arange(len(serie_m)), mean=serie_m, lb=serie_l, ub=serie_h, axis=ax, color_mean=c,
                                color_shading=col, label=l)
            # break

        Nticks = 5
        ticks = np.linspace(0, Npoints - 1, Nticks)
        # ax.locator_params(axis='x', nbins=Nticks)
        ax.set_xticks(ticks=ticks)
        ax.set_xticklabels(labels=[r'$0$', r'$\frac{\pi}{2}$', r'$\pi$', r'$\frac{3\pi}{2}$', r'$2\pi$'])
        ax.set_xlim([0, Npoints - 1])

        ax.set_ylabel(ylabels[i], fontsize=15)
        ax.set_xlabel('$\phi_{stride}$', fontsize=15)
        # axs.set_xlim([trange[0], trange[-1]])
        l = ax.legend(loc='upper right', fontsize=12)
        # plt.MaxNLocator(4)
        for j, text in enumerate(l.get_texts()):
            text.set_color(cs[i][j])
        plt.subplots_adjust(bottom=0.15, top=0.96, left=0.08, right=0.97, wspace=0.01)
        fig.savefig(filepaths[i], dpi=300)
        print(f'Plot saved as {filepaths[i]}')


def confidence_ellipse(x, y, ax, n_std=3.0, facecolor='none', **kwargs):
    """
    Create a plot of the covariance confidence ellipse of *x* and *y*.

    Parameters
    ----------
    x, y : array-like, shape (n, )
        Input data.

    ax : matplotlib.axes.Axes
        The axes object to draw the ellipse into.

    n_std : float
        The number of standard deviations to determine the ellipse's radiuses.

    **kwargs
        Forwarded to `~matplotlib.patches.Ellipse`

    Returns
    -------
    matplotlib.patches.Ellipse
    """
    if x.size != y.size:
        raise ValueError("x and y must be the same size")

    cov = np.cov(x, y)
    pearson = cov[0, 1] / np.sqrt(cov[0, 0] * cov[1, 1])
    # Using a special case to obtain the eigenvalues of this
    # two-dimensionl dataset.
    ell_radius_x = np.sqrt(1 + pearson)
    ell_radius_y = np.sqrt(1 - pearson)
    ellipse = mpatches.Ellipse((0, 0), width=ell_radius_x * 2, height=ell_radius_y * 2,
                               facecolor=facecolor, **kwargs)

    # Calculating the stdandard deviation of x from
    # the squareroot of the variance and multiplying
    # with the given number of standard deviations.
    scale_x = np.sqrt(cov[0, 0]) * n_std
    mean_x = np.mean(x)

    # calculating the stdandard deviation of y ...
    scale_y = np.sqrt(cov[1, 1]) * n_std
    mean_y = np.mean(y)

    transf = transforms.Affine2D() \
        .rotate_deg(45) \
        .scale(scale_x, scale_y) \
        .translate(mean_x, mean_y)

    ellipse.set_transform(transf + ax.transData)
    return ax.add_patch(ellipse)


def plot_correlated_pars(dataset, pars, labels, save_to=None, save_as=f'correlated_pars.{suf}', return_fig=False):
    if len(pars) != 3:
        raise ValueError('Currently implemented only for 3 parameters')
    if save_to is None:
        save_to = dataset.plot_dir
    e = dataset.endpoint_data
    # e = e[e['length'] > 2.5]
    g = sns.PairGrid(e[pars])
    g.map_upper(sns.scatterplot)
    g.map_lower(sns.kdeplot, fill=True)
    g.map_diag(sns.histplot, kde=True, bins=20)

    for i, ax in enumerate(g.axes[-1, :]):
        ax.xaxis.set_label_text(labels[i])
    for j, ax in enumerate(g.axes[:, 0]):
        ax.yaxis.set_label_text(labels[j])
    # g.axes[0,1].scatter(x=samples[1], y=samples[0], marker='.', color='r', alpha=0.1)
    for ax, (i, j) in zip([g.axes[0, 1], g.axes[0, 2], g.axes[1, 2]], [(1, 0), (2, 0), (2, 1)]):
        for std, a in zip([0.5, 1, 2, 3], [0.4, 0.3, 0.2, 0.1]):
            confidence_ellipse(x=e[pars[i]].values, y=e[pars[j]].values,
                               ax=ax, n_std=std, facecolor='red', alpha=a)
    return process_plot(g, save_to, save_as, return_fig)


def plot_ang_pars(datasets, labels, simVSexp=False, absolute=True, include_turns=False, include_rear=False,
                  save_to=None, Npars=3, legend=False, return_fig=False):
    Ndatasets, colors, save_to = plot_config(datasets, labels, save_to, subfolder='turn')
    if Npars == 5:
        par_shorts = ['b', 'bv', 'ba', 'fov', 'foa']
        ranges = [100, 200, 2000, 200, 2000]
        ylim = 0.1
    elif Npars == 3:
        par_shorts = ['b', 'bv', 'fov']
        ranges = [100, 200, 200]
        ylim = 0.05

    if include_rear:
        par_shorts += ['rov', 'roa']
        ranges += [200, 2000]
    if include_turns:
        par_shorts += ['tur_fo']
        ranges += [100]
    pars, sim_labels, exp_labels, xlabels = [
        par_db[['par', 'symbol', 'exp_symbol', 'unit']].loc[par_shorts].values[:, k].tolist() for k in range(4)]

    filename = f'angular_pars_{len(pars)}.{suf}'

    if simVSexp:
        p_labels = [[sl, el] for sl, el in zip(sim_labels, exp_labels)]
    else:
        p_labels = [[sl] * Ndatasets for sl in sim_labels]

    fig, axs = plt.subplots(1, len(pars), figsize=(len(pars) * 5, 5), sharey=True)
    axs = axs.ravel()
    nbins = 200

    for i, (p, r, p_lab, xlab) in enumerate(zip(pars, ranges, p_labels, xlabels)):
        for j, d in enumerate(datasets):
            v = d.get_par(p).dropna().values
            if absolute:
                v = np.abs(v)
                r1, r2 = 0, r
            else:
                r1, r2 = -r, r
            x = np.linspace(r1, r2, nbins)
            weights = np.ones_like(v) / float(len(v))
            # exp_weights = np.ones_like(exp) / float(len(exp))
            # sim_weights = np.ones_like(exp) / float(len(exp))
            # sns.distplot(exp, color="red", ax=axs[i], bins=x, hist=False, label=sim_labels[i],
            #              hist_kws={'weights': sim_weights})
            # sns.distplot(exp, color="blue", ax=axs[i], bins=x, hist=False, label=exp_labels[i],
            #              hist_kws={'weights': exp_weights})
            axs[i].hist(v, color=colors[j], bins=x, label=p_lab[j], weights=weights, alpha=0.5)
        axs[i].set_xlabel(xlab)
        axs[i].yaxis.set_major_locator(ticker.MaxNLocator(3))
        if legend:
            axs[i].legend()
    axs[0].set_ylabel('probability')
    axs[0].set_ylim([0, ylim])
    plt.subplots_adjust(bottom=0.15, top=0.95, left=0.3 / len(pars), right=0.99, wspace=0.01)
    return process_plot(fig, save_to, filename, return_fig)


def plot_crawl_pars(datasets, labels, simVSexp=False, save_to=None, legend=False, return_fig=False):
    Ndatasets, colors, save_to = plot_config(datasets, labels, save_to, subfolder='endpoint')
    filename = f'crawl_pars.{suf}'

    par_shorts = ['str_N', 'str_tr', 'cum_d']
    pars, sim_labels, exp_labels, xlabels = [
        par_db[['par', 'symbol', 'exp_symbol', 'unit']].loc[par_shorts].values[:, k].tolist() for k in range(4)]
    ranges = [(100, 300), (0.5, 1.0), (80, 320)]

    if simVSexp:
        p_labels = [[sl, el] for sl, el in zip(sim_labels, exp_labels)]
    else:
        p_labels = [[sl] * Ndatasets for sl in sim_labels]

    fig, axs = plt.subplots(1, len(pars), figsize=(len(pars) * 5, 5), sharey=True)
    axs = axs.ravel()
    nbins = 40
    for i, (p, r, p_lab, xlab) in enumerate(zip(pars, ranges, p_labels, xlabels)):
        r1, r2 = r[0], r[1]
        x = np.linspace(r1, r2, nbins)
        for j, d in enumerate(datasets):
            v = d.get_par(p).dropna().values
            # axs[i].set_xlim([-ranges[i], ranges[i]])
            # statistic, pvalue = ks_2samp(exp, exp)

            # weights = np.ones_like(vs) / float(len(vs))
            # exp_weights = np.ones_like(exp) / float(len(exp))
            # sim_weights = np.ones_like(exp) / float(len(exp))
            # sns.distplot(exp, color="red", ax=axs[i], bins=x, hist=False, label=sim_labels[i],
            #              kde=True)
            # sns.distplot(exp, color="blue", ax=axs[i], bins=x, hist=False, label=exp_labels[i],
            #              kde=True)
            # axs[i].hist(exp, color="red", bins=x, label=sim_labels[i],
            #             weights=sim_weights, alpha=0.5, histtype='stepfilled')
            # axs[i].hist(exp, color="blue", bins=x, label=exp_labels[i],
            #             weights=exp_weights, alpha=0.5, histtype='stepfilled')
            sns.histplot(v, color=colors[j], bins=x, kde=True, ax=axs[i], label=p_lab[j],
                         stat="probability", element="step")
        # sns.distplot(exp, color="red", bins=x, hist=False, ax=axs[i], label=sim_labels[i],
        #              norm_hist=True)
        # sns.distplot(exp, color="blue", bins=x, hist=False, ax=axs[i], label=exp_labels[i],
        #              norm_hist=True)
        axs[i].set_xlabel(xlab)
        # axs[i].set_ylim([0,0.2])
        axs[i].yaxis.set_major_locator(ticker.MaxNLocator(4))
        if legend:
            axs[i].legend(loc='upper right')
    axs[0].set_ylabel('probability')
    plt.subplots_adjust(bottom=0.15, top=0.95, left=0.25 / len(pars), right=0.99, wspace=0.01)
    return process_plot(fig, save_to, filename, return_fig)


def plot_endpoint_params(datasets, labels, mode='full', save_to=None, save_as=None, return_fig=False):
    warnings.filterwarnings('ignore')
    Ndatasets, colors, save_to = plot_config(datasets, labels, save_to, subfolder='endpoint')
    if save_as is None:
        filename = f'endpoint_params_{mode}.{suf}'
    else:
        filename = save_as
    fit_filename = 'endpoint_ttest.csv'
    fit_filepath = os.path.join(save_to, fit_filename)

    ylim = [0.0, 0.25]
    nbins = 20

    if mode == 'minimal':
        par_shorts = ['l_mu', 'fsv', 'sv_mu', 'str_sd_mu',
                      'cum_t', 'str_tr', 'pau_tr', 'tor',
                      'tor5_mu', 'tor20_mu', 'sdisp40_max', 'sdisp40_fin',
                      'b_mu', 'bv_mu', 'Ltur_tr', 'Rtur_tr']


    elif mode == 'limited':

        par_shorts = ['l_mu', 'fsv', 'sv_mu', 'str_sd_mu',
                      'cum_t', 'str_tr', 'pau_tr', 'pau_t_mu',
                      'tor5_mu', 'tor5_std', 'tor20_mu', 'tor20_std',
                      'tor', 'sdisp_mu', 'sdisp40_max', 'sdisp40_fin',
                      'b_mu', 'b_std', 'bv_mu', 'bv_std',
                      'Ltur_tr', 'Rtur_tr', 'Ltur_fo_mu', 'Rtur_fo_mu']


    elif mode == 'full':

        par_shorts = ['l_mu', 'str_N', 'str_rr', 'fsv',
                      'cum_d', 'cum_sd', 'v_mu', 'sv_mu',
                      'str_d_mu', 'str_d_std', 'str_sd_mu', 'str_sd_std',
                      'str_std_mu', 'str_std_std', 'str_sstd_mu', 'str_sstd_std',
                      'str_fo_mu', 'str_fo_std', 'str_ro_mu', 'str_ro_std',
                      'str_b_mu', 'str_b_std', 'str_t_mu', 'str_t_std',
                      'cum_t', 'str_tr', 'pau_tr', 'non_str_tr',
                      'pau_N', 'pau_t_mu', 'pau_t_std', 'tor',
                      'tor2_mu', 'tor5_mu', 'tor10_mu', 'tor20_mu',
                      'tor2_std', 'tor5_std', 'tor10_std', 'tor20_std',
                      'disp_mu', 'disp_fin', 'disp40_fin', 'disp40_max',
                      'sdisp_mu', 'sdisp_fin', 'sdisp40_fin', 'sdisp40_max',
                      'Ltur_t_mu', 'Ltur_t_std', 'cum_Ltur_t', 'Ltur_tr',
                      'Rtur_t_mu', 'Rtur_t_std', 'cum_Rtur_t', 'Rtur_tr',
                      'Ltur_fo_mu', 'Ltur_fo_std', 'Rtur_fo_mu', 'Rtur_fo_std',
                      'b_mu', 'b_std', 'bv_mu', 'bv_std',
                      ]

    elif mode == 'deb':

        par_shorts = [
            'deb_f_mu', 'hunger', 'reserve_density', 'puppation_buffer',
            'cum_d', 'cum_sd', 'str_N', 'fee_N',
            'str_tr', 'pau_tr', 'fee_tr', 'f_am',
            'l_mu', 'm'
            # 'tor2_mu', 'tor5_mu', 'tor10_mu', 'tor20_mu',
            # 'v_mu', 'sv_mu',

        ]

    pars, sim_labels, exp_labels, xlabels = [
        par_db[['par', 'symbol', 'exp_symbol', 'unit']].loc[par_shorts].values[:, k].tolist() for k in range(4)]
    pars = [p for p in pars if all([p in d.endpoint_data.columns for d in datasets])]

    if Ndatasets > 1:
        fit_ind = np.array([np.array([l1, l2]) for l1, l2 in itertools.combinations(labels, 2)])
        fit_ind = pd.MultiIndex.from_arrays([fit_ind[:, 0], fit_ind[:, 1]], names=('dataset1', 'dataset2'))
        fit_df = pd.DataFrame(index=fit_ind, columns=pars + [f'S_{p}' for p in pars] + [f'P_{p}' for p in pars])

    lw = 3
    Npars = len(pars)
    Ncols = 4
    Nrows = int(np.ceil(Npars / Ncols))
    fig, axs = plt.subplots(Nrows, Ncols, figsize=(5.5 * Ncols, 5 * Nrows), sharey=True)
    axs = axs.ravel()
    for i, p in enumerate(pars):
        values = [d.endpoint_data[p].values for d in datasets]
        # print(p)
        if Ndatasets > 1:
            for ind, (v1, v2) in zip(fit_ind, itertools.combinations(values, 2)):
                st, pv = ttest_ind(v1, v2, equal_var=False)
                signif = pv <= 0.01
                fit_df[f'S_{p}'].loc[ind] = st
                fit_df[f'P_{p}'].loc[ind] = np.round(pv, 11)
                fit_df[p].loc[ind] = signif

        Nvalues = [len(i) for i in values]
        a = np.empty((np.max(Nvalues), len(values),)) * np.nan
        for k in range(len(values)):
            a[:Nvalues[k], k] = values[k]
        df = pd.DataFrame(a, columns=labels)
        for j, (col, lab) in enumerate(zip(df.columns, labels)):
            try:
                v = df[[col]].dropna().values
                weights = np.ones_like(v) / float(len(v))
                y, x, patches = axs[i].hist(v, bins=nbins, weights=weights, color=colors[j], alpha=0.5)
                x = x[:-1] + (x[1] - x[0]) / 2
                y_smooth = np.polyfit(x, y, 5)
                poly_y = np.poly1d(y_smooth)(x)
                axs[i].plot(x, poly_y, color=colors[j], label=lab, linewidth=lw)
            except:
                pass
        if i % Ncols == 0:
            axs[i].set_ylabel('probability', fontsize=15)
        axs[i].set_title(p, fontsize=15)
        axs[i].xaxis.set_major_locator(ticker.MaxNLocator(4))
        axs[i].yaxis.set_major_locator(ticker.MaxNLocator(4))
        axs[i].xaxis.set_major_formatter(ScalarFormatter(useOffset=True, useMathText=True))
        # axs[i].ticklabel_format(axis='x', useMathText=True, scilimits=(-3, 3))
        # axs[i].ticklabel_format(axis='x', useMathText=True, scilimits=(-3, 3), useOffset=True)

        if Ndatasets > 1:
            for z, (l1, l2) in enumerate(fit_df[fit_df[p] == True].index.values):
                c1, c2 = colors[labels.index(l1)], colors[labels.index(l2)]
                rad = 0.04
                yy = 0.95 - z * 0.08
                xx = 0.7
                dual_half_circle(center=(xx, yy), radius=rad, angle=90, ax=axs[i], colors=(c1, c2),
                                 transform=axs[i].transAxes)
                pv = fit_df[f'P_{p}'].loc[(l1, l2)]
                if pv == 0:
                    pvi = -9
                else:
                    for pvi in np.arange(-1, -10, -1):
                        if np.log10(pv) > pvi:
                            pvi += 1
                            break
                axs[i].text(xx + 0.05, yy + rad / 1.5, f'p<10$^{{{pvi}}}$', ha='left', va='top', color='k', fontsize=15,
                            transform=axs[i].transAxes)

    plt.subplots_adjust(wspace=0.1, hspace=0.3, left=0.06, right=0.96, top=0.8, bottom=0.04)
    plt.ylim(ylim)
    leg = axs[0].legend(bbox_to_anchor=(Ncols / 2, 1.8), loc='upper center', prop={'size': 20})
    if Ndatasets > 1:
        fit_df.to_csv(fit_filepath, index=True, header=True)
        print(f'Tests saved as {fit_filename}.')
    return process_plot(fig, save_to, filename, return_fig)


def plot_turn_duration(datasets, labels, save_to=None, legend=False, absolute=True, return_fig=False):
    Ndatasets, colors, save_to = plot_config(datasets, labels, save_to, subfolder='turn')
    filename = f'turn_duration.{suf}'

    par_shorts = ['tur_fo', 'tur_t']
    pars, sim_labels, exp_labels, units = [
        par_db[['par', 'symbol', 'exp_symbol', 'unit']].loc[par_shorts].values[:, k].tolist() for k in range(4)]

    fig, axs = plt.subplots(1, 1, figsize=(5, 5))

    for d, l, c in zip(datasets, labels, colors):
        t = d.get_par(pars[0]).dropna().values.flatten()
        if absolute:
            t = np.abs(t)
        dur = d.get_par(pars[1]).dropna().values.flatten()
        plt.scatter(x=dur, y=t, marker='.', s=0.5, c=c, alpha=0.5, label=l)

        m, k = np.polyfit(dur, t, 1)
        # m = np.round(m, 3)
        # k = np.round(k, 3)
        # fits[label] = [m, k]
        axs.plot(dur, m * dur + k, linewidth=4, color=c)

    plt.xlabel(units[1])
    plt.ylabel(units[0])
    axs.yaxis.set_major_locator(ticker.MaxNLocator(4))
    if legend:
        plt.legend(loc='upper right')
    plt.subplots_adjust(bottom=0.15, top=0.95, left=0.2, right=0.95, wspace=0.01)
    return process_plot(fig, save_to, filename, return_fig)


def plot_turns(datasets, labels, save_to=None, return_fig=False):
    Ndatasets, colors, save_to = plot_config(datasets, labels, save_to, subfolder='turn')
    filename = f'turns.{suf}'
    fig, axs = plt.subplots(1, 1, figsize=(5, 5))

    par_short = 'tur_fo'
    par, sim_label, exp_label, xlabel = [par_db[['par', 'symbol', 'exp_symbol', 'unit']].loc[par_short].values[k] for k
                                         in range(4)]

    ts = []
    for d in datasets:
        t = d.get_par(par).dropna().values
        ts.append(t)

    r = 150
    Nbins = 150
    x = np.linspace(-r, r, Nbins)
    for data, col, l in zip(ts, colors, labels):
        weights = np.ones_like(data) / float(len(data))
        axs.hist(data, bins=x, weights=weights, label=l, color=col, alpha=1.0, histtype='step')

    axs.set_ylabel('probability, $P$')
    axs.set_xlabel(xlabel)
    axs.yaxis.set_major_locator(ticker.MaxNLocator(4))
    axs.legend(loc='upper right', fontsize=10)
    fig.subplots_adjust(top=0.92, bottom=0.15, left=0.2, right=0.95, hspace=.005, wspace=0.05)
    return process_plot(fig, save_to, filename, return_fig)


def comparative_analysis(datasets, labels, simVSexp=False, save_to=None):
    warnings.filterwarnings('ignore')
    Ndatasets = len(datasets)
    if save_to is None:
        save_to = datasets[0].comp_plot_dir
    config = {'datasets': datasets,
              'labels': labels,
              'save_to': save_to}
    for scaled in [True, False]:
        plot_dispersion(**config, scaled=scaled, fig_cols=2)
        plot_dispersion(**config, scaled=scaled, fig_cols=1)
    plot_stride_Dbend(**config, show_text=False)
    plot_stride_Dorient(**config, simVSexp=simVSexp, absolute=True)
    plot_ang_pars(**config, simVSexp=simVSexp, absolute=True, include_turns=False, Npars=3)
    # plot_ang_pars(**config, simVSexp=simVSexp, absolute=True, include_turns=False, Npars=5, include_rear=True)
    # plot_ang_pars(**config, simVSexp=simVSexp, absolute=True, include_turns=False, Npars=5)

    for r in ['broad']:
        # for r in ['default', 'restricted', 'broad']:
        plot_stridesNpauses(**config, plot_fits='all', time_unit='sec', range=r, only_fit_one=True)
        plot_stridesNpauses(**config, plot_fits='best', time_unit='sec', range=r)
    for mode in ['orientation', 'orientation_x2', 'bend', 'spinelength']:
        for agent_idx in [None, 0, 1]:
            try:
                plot_interference(**config, mode=mode, agent_idx=agent_idx)
            except:
                pass
    try:
        calibration_plot(save_to=save_to)
    except:
        pass
    plot_crawl_pars(**config, simVSexp=simVSexp)

    plot_turns(**config)
    plot_turn_duration(**config)

    for mode in ['minimal', 'limited', 'full']:
        plot_endpoint_params(**config, mode=mode)
    combine_pdfs(file_dir=save_to)


def dual_half_circle(center, radius, angle=0, ax=None, colors=('w', 'k'), **kwargs):
    """
    Add two half circles to the axes *ax* (or the current axes) with the
    specified facecolors *colors* rotated at *angle* (in degrees).
    """
    if ax is None:
        ax = plt.gca()
    theta1, theta2 = angle, angle + 180
    w1 = Wedge(center, radius, theta1, theta2, fc=colors[0], **kwargs)
    w2 = Wedge(center, radius, theta2, theta1, fc=colors[1], **kwargs)
    for wedge in [w1, w2]:
        ax.add_artist(wedge)
    return [w1, w2]


def save_plot(fig, filepath, filename=None):
    fig.savefig(filepath, dpi=300, facecolor=None)
    # print(fig.get_size_inches(), filename)
    fig.clear()
    plt.close(fig)
    if filename is not None:
        print(f'Plot saved as {filename}')


def plot_config(datasets, labels, save_to, subfolder=None):
    Ndatasets = len(datasets)
    if Ndatasets != len(labels):
        raise ValueError('Number of labels does not much number of datasets')
    colors = N_colors(Ndatasets)
    if save_to is None:
        save_to = datasets[0].comp_plot_dir
    if subfolder is not None:
        save_to = f'{save_to}/{subfolder}'
    if not os.path.exists(save_to):
        os.makedirs(save_to)
    return Ndatasets, colors, save_to


def plot_endpoint_scatter(datasets, labels, save_to=None, par_shorts=None, return_fig=False):
    Ndatasets, colors, save_to = plot_config(datasets, labels, save_to)

    pairs = list(itertools.combinations(par_shorts, 2))
    Npairs = len(pairs)
    if Npairs % 3 == 0:
        Nx, Ny = 3, int(Npairs / 3)
    elif Npairs % 2 == 0:
        Nx, Ny = 2, int(Npairs / 2)
    elif Npairs % 5 == 0:
        Nx, Ny = 5, int(Npairs / 5)
    else:
        Nx, Ny = Npairs, 1
    fig, axs = plt.subplots(Nx, Ny, figsize=(10 * Ny, 10 * Nx))
    if Nx * Ny > 1:
        axs = axs.ravel()
        filename = f'endpoint_scatterplot.{suf}'
    else:
        axs = [axs]
        filename = f'{par_shorts[1]}_vs_{par_shorts[0]}.{suf}'
    filepath = os.path.join(save_to, filename)
    for i, (p0, p1) in enumerate(pairs):
        ax = axs[i]
        pars, sim_labels, exp_labels, units = [
            par_db[['par', 'symbol', 'exp_symbol', 'unit']].loc[[p0, p1]].values[:, k].tolist() for k in range(4)]

        v0_all = [d.endpoint_data[pars[0]].values for d in datasets]
        v1_all = [d.endpoint_data[pars[1]].values for d in datasets]
        r0, r1 = 0.9, 1.1
        v0_r = [np.min(np.array(v0_all)) * r0, np.max(np.array(v0_all)) * r1]
        v1_r = [np.min(np.array(v1_all)) * r0, np.max(np.array(v1_all)) * r1]

        for v0, v1, l, c in zip(v0_all, v1_all, labels, colors):
            ax.scatter(v0, v1, color=c, label=l)
        ax.set_title(f'{pars[1]}_vs_{pars[0]}', fontsize=20)
        ax.legend()
        ax.set_xlabel(units[0])
        ax.set_ylabel(units[1])
        ax.set_xlim(v0_r)
        ax.set_ylim(v1_r)
        ax.ticklabel_format(useMathText=True, scilimits=(0, 0))
    save_plot(fig, filepath, filename)


def plot_nengo(d, save_to=None):
    if save_to is None:
        save_to = d.plot_dir
    s = d.step_data.xs(d.agent_ids[0], level='AgentID')
    t = np.linspace(0, d.num_ticks * d.dt, d.num_ticks)
    filename = f'nengo.{suf}'
    filepath = os.path.join(save_to, filename)

    pars = [['crawler_activity', 'turner_activity'], ['crawler_activity', 'feeder_motion']]
    labels = [['crawler', 'turner'], ['crawler', 'feeder']]
    colors = [['blue', 'red'], ['blue', 'green']]

    try:
        chunk1 = 'pause'
        pau1s = s.index[s[f'{chunk1}_stop'] == True] * d.dt
        pau0s = s.index[s[f'{chunk1}_start'] == True] * d.dt
        pause = True
    except:
        pause = False
    try:
        chunk2 = 'stride'
        str1s = s.index[s[f'{chunk2}_stop'] == True] * d.dt
        str0s = s.index[s[f'{chunk2}_start'] == True] * d.dt
        stride = True
    except:
        stride = False
    fig, axs = plt.subplots(2, 1, figsize=(20, 5))
    axs = axs.ravel()
    for ax1, (p1, p2), (l1, l2), (c1, c2) in zip(axs, pars, labels, colors):
        # ax1=axs[0]
        ax2 = ax1.twinx()
        ax1.plot(t, s[p1], color=c1, label=l1)
        ax2.plot(t, s[p2], color=c2, label=l2)
        ax1.legend(loc='upper left')
        ax2.legend(loc='upper right')

        if pause:
            for start, stop in zip(pau0s, pau1s):
                plt.axvspan(start, stop, color='grey', alpha=0.3)
        if stride:
            for start, stop in zip(str0s, str1s):
                plt.axvspan(start, stop, color='blue', alpha=0.3)
    plt.xlabel(r'time $(sec)$')
    save_plot(fig, filepath, filename)


def process_plot(fig, save_to, filename, return_fig):
    fig.patch.set_visible(False)
    if return_fig:
        return fig, save_to, filename
    else:
        filepath = os.path.join(save_to, filename)
        save_plot(fig, filepath, filename)
        return None


def barplot(datasets, labels, par_shorts=['f_am'], coupled_labels=None, xlabel=None, ylabel=None, save_to=None,
            save_as=None,
            return_fig=False):
    Ndatasets, colors, save_to = plot_config(datasets, labels, save_to)
    w = 0.1

    if coupled_labels is not None:
        Npairs = len(coupled_labels)
        N = int(Ndatasets / Npairs)
        leg_cols = N_colors(N)
        colors = leg_cols * Npairs
        leg_ids = labels[:N]
        ind = np.hstack([np.linspace(0 + i / N, w + i / N, N) for i in range(Npairs)])
        new_ind = ind[::N] + (ind[N - 1] - ind[0]) / N
    else:
        ind = np.arange(0, w * Ndatasets, w)

    if save_as is None:
        filename = f'barplot.{suf}'
    else:
        filename = save_as

    pars, sim_labels, exp_labels, units = [
        par_db[['par', 'symbol', 'exp_symbol', 'unit']].loc[par_shorts].values[:, k].tolist() for k in range(4)]

    # Pull the formatting out here
    bar_kwargs = {'width': w, 'color': colors, 'linewidth': 4, 'zorder': 5, 'align': 'center'}
    err_kwargs = {'zorder': 20, 'fmt': 'none', 'linewidth': 4, 'ecolor': 'k', 'barsabove': True, 'capsize': 10}

    es = [d.endpoint_data for d in datasets]

    for p, u in zip(pars, units):
        values = [e[p] for e in es]
        means = [v.mean() for v in values]
        stds = [v.std() for v in values]
        fig, ax = plt.subplots(figsize=(10, 10))
        ax.p1 = plt.bar(ind, means, **bar_kwargs)
        ax.errs = plt.errorbar(ind, means, yerr=stds, **err_kwargs)

        if not coupled_labels:
            for i, j in itertools.combinations(np.arange(Ndatasets).tolist(), 2):
                st, pv = ttest_ind(values[i], values[j], equal_var=False)
                pv = np.round(pv, 4)
                label_diff(i, j, f'p={pv}', ind, means, ax)
        else:
            for k in range(Npairs):
                i, j = k * N, k * N + 1
                st, pv = ttest_ind(values[i], values[j], equal_var=False)
                if pv <= 0.05:
                    ax.text(ind[j], means[j] + stds[j], '*', ha='center', fontsize=20)
                    # label_diff(i, j, '*', ind, means, ax)

        h = 2 * (np.nanmax(means) + np.nanmax(stds))
        ax.yaxis.set_major_locator(ticker.MaxNLocator(4))
        ax.ticklabel_format(axis='y', useMathText=True, scilimits=(-3, 3), useOffset=True)
        if coupled_labels is None:
            plt.xticks(ind, labels, color='k')
        else:
            plt.xticks(new_ind, coupled_labels, color='k')
            plt.legend(handles=[mpatches.Patch(color=c, label=id) for c, id in zip(leg_cols, leg_ids)],
                       labels=leg_ids, fontsize=20, loc='upper right', prop={'size': 10})
        if ylabel is None:
            plt.ylabel(u)
        else:
            plt.ylabel(ylabel)
        plt.ylim(0, h)
        if xlabel is not None:
            plt.xlabel(xlabel)
        return process_plot(fig, save_to, filename, return_fig)


def label_diff(i, j, text, X, Y, ax):
    x = (X[i] + X[j]) / 2
    y = 1.5 * max(Y[i], Y[j])
    dx = abs(X[i] - X[j])

    props = {'connectionstyle': 'bar', 'arrowstyle': '-', \
             'shrinkA': 20, 'shrinkB': 20, 'linewidth': 2}
    ax.annotate(text, xy=(X[i], y), zorder=10)
    # ax.annotate(text, xy=(X[i], y), zorder=10)
    ax.annotate('', xy=(X[i], y), xytext=(X[j], y), arrowprops=props)


def calibration_plot(save_to=None, files=None):
    # plt.tick_params(
    tick_params = {
        'axis': 'both',  # changes apply to the x-axis
        'which': 'both',  # both major and minor ticks are affected
        'bottom': False,  # ticks along the bottom edge are off
        'top': False,  # ticks along the top edge are off
        'labelbottom': False,  # labels along the bottom edge are off
        'labeltop': False,
        'labelleft': False,
        'labelright': False,
    }

    filename = 'calibration.pdf'
    fig = plt.figure(constrained_layout=True, figsize=(6 * 5, 2 * 5))
    gs = fig.add_gridspec(2, 6)
    interference = fig.add_subplot(gs[:, :2])
    bouts = fig.add_subplot(gs[0, 2:4])
    orient = fig.add_subplot(gs[0, 4:])
    angular = fig.add_subplot(gs[1, 3:])
    bend = fig.add_subplot(gs[1, 2])

    if save_to is None:
        save_to = '.'
    if files is None:
        filenames = [
            'interference/interference_orientation.png',
            'bouts/stridesNpauses_cdf_restricted_0.png',
            'stride/stride_orient_change.png',
            'turn/angular_pars_3.png',
            'stride/stride_bend_change.png'
        ]
        files = [f'{save_to}/{f}' for f in filenames]
    images = [Image.open(f) for f in files]
    axes = [interference, bouts, orient, angular, bend]
    for ax, im in zip(axes, images):
        ax.tick_params(**tick_params)
        ax.axis('off')
        ax.imshow(im, cmap=None, aspect=None)
    filepath = os.path.join(save_to, filename)
    save_plot(fig, filepath, filename)

